import logging
import os
import re
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from GAVEL.infra.asu_auth.browser_session import BROWSER_ERRORS, AsuBrowserSession, host_of
from GAVEL.services.env_service import SCHEMA_DEFAULTS

# -------------------------
# Logging Setup
# -------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GradescopeClient")


def _env_or_default(name: str) -> str | None:
    """Return the env var if set & non-empty, otherwise the schema default."""
    value = os.getenv(name)
    if value:
        return value
    return SCHEMA_DEFAULTS.get(name)


# -------------------------
# Data Class
# -------------------------


@dataclass
class GradescopeSession:
    session_cookie: str
    token: str | None
    all_cookies: dict[str, str]


# -------------------------
# Main Bridge Class
# -------------------------


def remove_illegal_download_characters(name: str) -> str:
    safe_name = re.sub(r'[\\/:*?"<>|]', "", name)
    return safe_name


class http_gradescope_client:
    """
    ASU-specific Canvas → CAS → Duo → Canvas → Gradescope bridge.

    The ASU login itself is done by the shared login browser when one is
    passed in, so a login made earlier (by another download, or in a previous
    run of the app) is reused instead of repeated.
    """

    GRADESCOPE_DOMAIN = "www.gradescope.com"
    SESSION_COOKIE_NAME = "_gradescope_session"
    TOKEN_COOKIE_NAME = "token"

    def __init__(
        self,
        course_url: str,
        headless: bool = True,
        submissions_folder: str | None = None,
        browser: AsuBrowserSession | None = None,
    ):

        load_dotenv()

        self.course_url = course_url
        self.headless = headless
        self._browser = browser
        self._driver = None  # the borrowed browser, only while capture_session runs

        self.base_url = _env_or_default("GRADESCOPE_BASE_URL")
        self.courses_suffix = _env_or_default("GRADESCOPE_COURSES_SUFFIX")
        self.assignments_suffix = _env_or_default("GRADESCOPE_ASSIGNMENTS_SUFFIX")
        self.review_grades_suffix = _env_or_default("GRADESCOPE_REVIEW_GRADES_SUFFIX")
        self.generated_files_suffix = _env_or_default("GRADESCOPE_GENERATED_FILES_SUFFIX")
        self.submissions_folder = submissions_folder or os.getenv("SUBMISSIONS_FOLDER")

        env_variables = [
            (self.base_url, "GRADESCOPE_BASE_URL"),
            (self.courses_suffix, "GRADESCOPE_COURSES_SUFFIX"),
            (self.assignments_suffix, "GRADESCOPE_ASSIGNMENTS_SUFFIX"),
            (self.review_grades_suffix, "GRADESCOPE_REVIEW_GRADES_SUFFIX"),
            (self.generated_files_suffix, "GRADESCOPE_GENERATED_FILES_SUFFIX"),
            (self.submissions_folder, "SUBMISSIONS_FOLDER"),
        ]
        empty_env_variables = []
        for e in env_variables:
            if None in e:
                empty_env_variables.append(e[-1])
        if empty_env_variables:
            log.error(f"Certain required environment variables are empty: {empty_env_variables}")
            raise ValueError(
                f"Certain required environment variables are empty: {empty_env_variables}"
            )
        if not self.submissions_folder:
            raise ValueError(
                "SUBMISSIONS_FOLDER is required. Set it in .env or pass an output "
                "folder via the download page."
            )
        if os.getenv("CANVAS_USERNAME") is None or os.getenv("CANVAS_PASSWORD") is None:
            log.warning(
                "NOTICE: You can add your Canvas login as CANVAS_USERNAME and CANVAS_PASSWORD in your .env file for easier login!"
            )

    # -------------------------
    # Canvas → Gradescope
    # -------------------------

    def _open_gradescope_from_course_nav(self, wait: WebDriverWait, starting_tabs: list[str]):
        log.debug("Waiting for Canvas course nav to load...")
        wait.until(ec.presence_of_element_located((By.ID, "section-tabs")))

        log.debug("Clicking Gradescope nav link...")
        nav_link = wait.until(
            ec.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Gradescope')]"))
        )
        nav_link.click()

        log.debug("Waiting for new Gradescope tab...")
        wait.until(lambda d: any(h not in starting_tabs for h in d.window_handles))

        new_tab = next(h for h in self._driver.window_handles if h not in starting_tabs)
        self._driver.switch_to.window(new_tab)
        log.debug("Switched to Gradescope tab...")

    def _close_extra_tabs(self, starting_tabs: list[str], home_tab: str) -> None:
        """Leave the shared browser as it was found: one tab, focused."""
        try:
            for handle in self._driver.window_handles:
                if handle not in starting_tabs:
                    self._driver.switch_to.window(handle)
                    self._driver.close()
            self._driver.switch_to.window(home_tab)
        except BROWSER_ERRORS as exc:
            log.debug("Could not tidy up browser tabs: %s", exc)

    # -------------------------
    # Extract Cookies
    # -------------------------

    def _extract_session(self) -> GradescopeSession:
        log.debug("Extracting Gradescope cookies...")

        raw_cookies = self._driver.get_cookies()
        cookies = {c["name"]: c["value"] for c in raw_cookies}
        log.debug("Cookies found: %s", cookies)

        session_cookie = cookies.get("_gradescope_session")
        token = cookies.get("token")

        if not session_cookie:
            log.error("Gradescope session cookie not found.")
            raise RuntimeError("Gradescope session cookie not found.")

        return GradescopeSession(
            session_cookie=session_cookie,
            token=token,
            all_cookies=cookies,
        )

    # -------------------------
    # Main Flow
    # -------------------------

    def capture_session(
        self, username: str, password: str, timeout: int = 40
    ) -> tuple[GradescopeSession, str]:
        """Reach Gradescope through Canvas and return its session and course ID.

        With a shared login browser the ASU login happens only if that browser
        is not signed in already. Without one, a private browser is opened
        for this call and closed afterwards.
        """
        browser = self._browser or AsuBrowserSession()
        try:
            with browser.use(headless=self.headless) as driver:
                self._driver = driver
                try:
                    return self._capture(browser, username, password, timeout)
                finally:
                    self._driver = None
        finally:
            if browser is not self._browser:
                browser.close()

    def _capture(
        self, browser: AsuBrowserSession, username: str, password: str, timeout: int
    ) -> tuple[GradescopeSession, str]:
        driver = self._driver
        wait = WebDriverWait(driver, timeout)
        starting_tabs = list(driver.window_handles)
        home_tab = driver.current_window_handle

        try:
            log.debug("Navigating to Canvas course: %s", self.course_url)
            driver.get(self.course_url)

            # Lands on the course page straight away when already signed in;
            # otherwise CAS + Duo happen here.
            credentials = (username, password) if username and password else None
            browser.wait_for_login(driver, self._on_canvas_course_page, credentials=credentials)

            # Click Gradescope
            self._open_gradescope_from_course_nav(wait, starting_tabs)

            # Wait for Gradescope
            log.debug("Waiting for Gradescope to load...")
            wait.until(lambda d: host_of(d.current_url) == self.GRADESCOPE_DOMAIN)

            time.sleep(2)

            gs_course_id = self._extract_gradescope_course_id()
            log.debug("Detected Gradescope course ID: %s", gs_course_id)

            return self._extract_session(), gs_course_id

        except TimeoutException as e:
            log.error("Timed out during SSO flow at URL: %s", driver.current_url)
            raise RuntimeError(
                f"Timed out during SSO flow. Current URL: {driver.current_url}"
            ) from e

        finally:
            self._close_extra_tabs(starting_tabs, home_tab)

    @staticmethod
    def _on_canvas_course_page(driver) -> bool:
        return bool(driver.find_elements(By.ID, "section-tabs"))

    def _extract_gradescope_course_id(self) -> str:
        """
        Extracts the Gradescope course ID from the current URL.
        Works for all URL shapes:
          /courses/<id>
          /courses/<id>/assignments
          /courses/<id>/assignments/<assignment_id>/review_grades
        """
        url = self._driver.current_url
        parts = url.split("/")

        if "courses" not in parts:
            log.error(f"Could not find 'courses' in URL: {url}")
            raise RuntimeError(f"Could not find 'courses' in URL: {url}")

        course_id = parts[parts.index("courses") + 1]
        return course_id

    def _build_requests_session(
        self, gs_session: GradescopeSession, course_id: int | str
    ) -> requests.Session:
        session = requests.Session()

        # Copy all cookies from Selenium
        for name, value in gs_session.all_cookies.items():
            session.cookies.set(name, value, domain=self.GRADESCOPE_DOMAIN)

        # Browser-like headers
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Referer": f"{self.base_url}{self.courses_suffix}/{course_id}",
            }
        )

        # CSRF token if present
        if gs_session.token:
            session.headers["X-CSRF-Token"] = gs_session.token

        return session

    def download_all_assignments(self, username: str, password: str) -> list[str]:
        """Log in, then save every assignment's bulk export and autograder to submissions_folder.

        Files are named ``<assignment name>.zip`` and ``<assignment name>_autograder.zip``
        (illegal filename characters removed). Where they belong in the workspace is the
        caller's business: DownloadGradescopeSubmissionsUseCase files them by Canvas
        assignment. Returns the paths written.
        """
        log.info("Downloading all assignments...")
        gs_session, gs_course_id = self.capture_session(username, password)
        session = self._build_requests_session(gs_session, course_id=gs_course_id)
        os.makedirs(self.submissions_folder, exist_ok=True)

        # Fetch assignments list
        resp = session.get(
            f"{self.base_url}{self.courses_suffix}/{gs_course_id}{self.assignments_suffix}"
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        elements = soup.find_all(
            attrs={"data-assignment-id": True, "aria-describedby": f"course-{gs_course_id}"}
        )
        assignments = {e.get_text(strip=True): e["data-assignment-id"] for e in elements}

        written: list[str] = []
        for name, assignment_id in assignments.items():
            safe_name = remove_illegal_download_characters(name)
            assignment_url = (
                f"{self.base_url}{self.courses_suffix}/{gs_course_id}"
                f"{self.assignments_suffix}/{assignment_id}"
            )

            # The autograder attached to the assignment, when there is one.
            resp = session.get(f"{assignment_url}/configure_autograder")
            soup = BeautifulSoup(resp.text, "html.parser")
            link = soup.find("a", string=lambda t: t and "Download Autograder" in t)
            if link and ".zip" in link["href"]:
                log.info("Downloading autograder for assignment: %s", name)
                autograder_download = session.get(link["href"])
                written.append(
                    self._save(f"{safe_name}_autograder.zip", autograder_download.content)
                )

            # The bulk export of submissions: reuse an existing export or trigger one.
            review_url = f"{assignment_url}{self.review_grades_suffix}"
            resp = session.get(review_url)
            soup = BeautifulSoup(resp.text, "html.parser")
            link = soup.find("a", class_="js-bulkExportModalDownload")

            if link and ".zip" in link["href"]:
                log.info("Downloading assignment: %s", name)
                zip_resp = session.get(f"{self.base_url}{link['href']}")
            else:
                log.info("Export not created yet; exporting assignment: %s", assignment_id)
                csrf = soup.find("meta", attrs={"name": "csrf-token"})["content"]
                session.headers["X-CSRF-Token"] = csrf
                export_resp = session.post(
                    f"{assignment_url}/export", headers={"Referer": review_url}
                )
                file_id = export_resp.json()["generated_file_id"]

                generated = (
                    f"{self.base_url}{self.courses_suffix}/{gs_course_id}"
                    f"{self.generated_files_suffix}/{file_id}"
                )
                while True:
                    progress = session.get(f"{generated}.json").json()["progress"]
                    if progress == 1.0:
                        log.info("Export completed!")
                        break
                    log.info("Waiting for export... (%s%%)", int(progress * 100))
                    time.sleep(1.5)
                zip_resp = session.get(f"{generated}.zip")

            written.append(self._save(f"{safe_name}.zip", zip_resp.content))
            log.info("Assignment %s downloaded!", name)

        log.info("Download of class %s complete!", gs_course_id)
        return written

    def _save(self, filename: str, content: bytes) -> str:
        output_path = os.path.join(self.submissions_folder, filename)
        with open(output_path, "wb") as f:
            f.write(content)
        return output_path


def main():
    return


#     if len(sys.argv) != 2 or not sys.argv[1].isdigit():
#         log.error("ERROR: Must enter courseID as integer for argument!")
#         return
#
#     course_id = int(sys.argv[1])
#     client = GradescopeClient(
#         course_url=f"https://canvas.asu.edu/courses/{course_id}", headless=False
#     )
#
#     client.download_all_assignments(
#         username=os.getenv("CANVAS_USERNAME"),
#         password=os.getenv("CANVAS_PASSWORD"),
#     )
#
#
# if __name__ == "__main__":
#     main()
