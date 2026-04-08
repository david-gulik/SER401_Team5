import logging
import os
import re
import sys
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

# -------------------------
# Logging Setup
# -------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GradescopeClient")

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


class GradescopeClient:
    """
    ASU-specific Canvas → CAS → Duo → Canvas → Gradescope bridge.
    """

    GRADESCOPE_DOMAIN = "www.gradescope.com"
    SESSION_COOKIE_NAME = "_gradescope_session"
    TOKEN_COOKIE_NAME = "token"

    def __init__(self, course_url: str, headless: bool = True):

        load_dotenv()

        self.course_url = course_url
        self.headless = headless
        self._driver: webdriver.Chrome | None = None  # noqa:

        self.base_url = os.getenv("GRADESCOPE_BASE_URL")
        self.courses_suffix = os.getenv("GRADESCOPE_COURSES_SUFFIX")
        self.assignments_suffix = os.getenv("GRADESCOPE_ASSIGNMENTS_SUFFIX")
        self.review_grades_suffix = os.getenv("GRADESCOPE_REVIEW_GRADES_SUFFIX")
        self.generated_files_suffix = os.getenv("GRADESCOPE_GENERATED_FILES_SUFFIX")

    # -------------------------
    # Driver
    # -------------------------

    def _build_driver(self) -> webdriver.Chrome:
        log.info("Building Chrome driver... (headless=%s)", self.headless)

        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        return webdriver.Chrome(options=options)

    def _handle_duo(self, wait: WebDriverWait):
        """
        Clicks:
          - "No, other people use this device"
        """

        log.info("Checking for Duo Prompt...")

        try:
            no_btn = wait.until(
                ec.element_to_be_clickable(
                    (By.XPATH, "//*[contains(text(), 'No, other people use this device')]")
                )
            )
            log.info("Clicking 'No, other people use this device'...")
            no_btn.click()
        except TimeoutException:
            log.info("No trusted device prompt detected.")

    # -------------------------
    # CAS Login
    # -------------------------

    def _handle_cas_login(self, wait: WebDriverWait, username: str, password: str):
        if "weblogin.asu.edu" not in self._driver.current_url:
            return

        log.info("Performing CAS login...")

        user_field = wait.until(ec.presence_of_element_located((By.ID, "username")))
        pass_field = self._driver.find_element(By.ID, "password")

        user_field.send_keys(username)
        pass_field.send_keys(password)

        log.info("Submitting CAS login form...")
        self._driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self._handle_duo(wait)
        log.info("CAS login + Duo complete.")

    # -------------------------
    # Canvas → Gradescope
    # -------------------------

    def _open_gradescope_from_course_nav(self, wait: WebDriverWait):
        log.info("Waiting for Canvas course nav to load...")
        wait.until(ec.presence_of_element_located((By.ID, "section-tabs")))

        log.info("Clicking Gradescope nav link...")
        nav_link = wait.until(
            ec.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Gradescope')]"))
        )
        nav_link.click()

        log.info("Waiting for new Gradescope tab...")
        wait.until(lambda d: len(d.window_handles) > 1)

        handles = self._driver.window_handles
        self._driver.switch_to.window(handles[-1])
        log.info("Switched to Gradescope tab...")

    # -------------------------
    # Extract Cookies
    # -------------------------

    def _extract_session(self) -> GradescopeSession:
        log.info("Extracting Gradescope cookies...")

        raw_cookies = self._driver.get_cookies()
        cookies = {c["name"]: c["value"] for c in raw_cookies}
        log.info("Cookies found: %s", cookies)

        session_cookie = cookies.get("_gradescope_session")
        token = cookies.get("token")

        if not session_cookie:
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
        self._driver = self._build_driver()
        wait = WebDriverWait(self._driver, timeout)

        try:
            log.info("Navigating to Canvas course: %s", self.course_url)
            self._driver.get(self.course_url)
            time.sleep(1)

            # CAS login if redirected
            if "weblogin.asu.edu" in self._driver.current_url:
                self._handle_cas_login(wait, username, password)

            wait.until(ec.presence_of_element_located((By.ID, "section-tabs")))

            # Click Gradescope
            self._open_gradescope_from_course_nav(wait)

            # Wait for Gradescope
            log.info("Waiting for Gradescope to load...")
            wait.until(lambda d: self.GRADESCOPE_DOMAIN in d.current_url)

            time.sleep(2)

            gs_course_id = self._extract_gradescope_course_id()
            log.info("Detected Gradescope course ID: %s", gs_course_id)

            return self._extract_session(), gs_course_id

        except TimeoutException as e:
            log.error("Timed out during SSO flow at URL: %s", self._driver.current_url)
            raise RuntimeError(
                f"Timed out during SSO flow. Current URL: {self._driver.current_url}"
            ) from e

        finally:
            log.info("Cookies extracted! Closing browser...")
            self._driver.quit()

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

    # ---------------------------------------------------------
    # NEW: Downloader (moved from global function)
    # ---------------------------------------------------------
    def download_all_assignments(self, username: str, password: str):
        """
        Logs in, captures session, and downloads all assignment bulk exports.
        """

        gs_session, gs_course_id = self.capture_session(username, password)
        session = self._build_requests_session(gs_session, course_id=gs_course_id)

        # Fetch assignments list
        resp = session.get(
            f"{self.base_url}{self.courses_suffix}/{gs_course_id}{self.assignments_suffix}"
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        elements = soup.find_all(attrs={"data-assignment-id": True})

        assignments = {e.get_text(strip=True): e["data-assignment-id"] for e in elements}

        sub_folder = os.getenv("SUBMISSIONS_FOLDER")

        for name, assignment_id in assignments.items():
            review_url = f"{self.base_url}{self.courses_suffix}/{gs_course_id}{self.assignments_suffix}/{assignment_id}{self.review_grades_suffix}"
            resp = session.get(review_url)
            soup = BeautifulSoup(resp.text, "html.parser")

            link = soup.find("a", class_="js-bulkExportModalDownload")

            # Case 1: Export already exists
            if link and ".zip" in link["href"]:
                log.info("Downloading assignment: %s", name)
                zip_resp = session.get(f"{self.base_url}" + link["href"])

                safe_name = re.sub(r'[\\/:*?"<>|]', "", name)
                output_path = os.path.join(sub_folder, safe_name + ".zip")

                with open(output_path, "wb") as f:
                    f.write(zip_resp.content)

                log.info("Assignment %s downloaded!", name)
                continue

            # Case 2: Need to trigger export
            log.info("Export not created yet; exporting assignment: %s", assignment_id)

            csrf = soup.find("meta", attrs={"name": "csrf-token"})["content"]
            session.headers["X-CSRF-Token"] = csrf

            export_resp = session.post(
                f"{self.base_url}{self.courses_suffix}/{gs_course_id}{self.assignments_suffix}/{assignment_id}/export",
                headers={"Referer": review_url},
            )
            data = export_resp.json()
            file_id = data["generated_file_id"]

            # Polling
            poll_url = f"{self.base_url}{self.courses_suffix}/{gs_course_id}{self.generated_files_suffix}/{file_id}.json"

            while True:
                poll_resp = session.get(poll_url)
                poll_data = poll_resp.json()
                progress = poll_data["progress"]

                if progress == 1.0:
                    log.info("Export completed!")
                    break

                log.info("Waiting for export... (%s%%)", int(progress * 100))
                time.sleep(1)

            # Download final ZIP
            zip_url = f"{self.base_url}{self.courses_suffix}/{gs_course_id}{self.generated_files_suffix}/{file_id}.zip"
            zip_resp = session.get(zip_url)

            safe_name = re.sub(r'[\\/:*?"<>|]', "", name)
            output_path = os.path.join(sub_folder, safe_name + ".zip")

            with open(output_path, "wb") as f:
                f.write(zip_resp.content)

            log.info("Assignment %s downloaded!", assignment_id)

        log.info("Download of class %s complete!", gs_course_id)


def main():

    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        log.error("ERROR: Must enter courseID as integer for argument!")
        return

    course_id = int(sys.argv[1])
    client = GradescopeClient(
        course_url=f"https://canvas.asu.edu/courses/{course_id}", headless=False
    )

    client.download_all_assignments(
        username=os.getenv("CANVAS_USERNAME"),
        password=os.getenv("CANVAS_PASSWORD"),
    )


if __name__ == "__main__":
    main()
