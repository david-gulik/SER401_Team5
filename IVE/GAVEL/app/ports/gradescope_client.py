import logging
import os
import re
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
        self.course_url = course_url
        self.headless = headless
        self._driver: webdriver.Chrome | None = None  # noqa:

    # -------------------------
    # Driver
    # -------------------------

    def _build_driver(self) -> webdriver.Chrome:
        log.info("Building Chrome driver (headless=%s)", self.headless)

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

        # user_field = wait.until(ec.presence_of_element_located((By.ID, "username")))
        # pass_field = self._driver.find_element(By.ID, "password")

        # user_field.send_keys(username)
        # pass_field.send_keys(password)

        log.info("Submitting CAS login form...")
        # self._driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
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
            ec.element_to_be_clickable((By.ID, "context_external_tool_171355-link"))
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


def build_requests_session(gs_session: GradescopeSession, course_id: int | str) -> requests.Session:
    session = requests.Session()

    # Find all pesky little hidden cookies
    for name, value in gs_session.all_cookies.items():
        session.cookies.set(name, value, domain="www.gradescope.com")

    # Headers that make the request look like the browser
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": f"https://www.gradescope.com/courses/{course_id}",
        }
    )

    # extract the CSRF token
    if gs_session.token:
        session.headers["X-CSRF-Token"] = gs_session.token

    return session


# -------------------------
# Downloader Function: takes in a course_id as an argument and downloads all assignment bulk submission zips to [TBD]
# -------------------------


def gs_downloader(course_id: int):
    load_dotenv()

    bridge = GradescopeClient(
        course_url=f"https://canvas.asu.edu/courses/{course_id}", headless=False
    )

    # TODO: Clean this up, decide on login process

    gs_session, gs_course_id = bridge.capture_session(
        username="ENTERYOURUSERNAME",  # noqa:
        password="ENTERYOURPASSWORD",  # noqa:
    )

    session = build_requests_session(gs_session, course_id=gs_course_id)

    # Fetch assignments

    resp = session.get(f"https://www.gradescope.com/courses/{gs_course_id}/assignments")
    soup = BeautifulSoup(resp.text, "html.parser")
    elements = soup.find_all(attrs={"data-assignment-id": True})
    assignments = {}
    for e in elements:
        assignments[e.get_text(strip=True)] = e["data-assignment-id"]

    sub_folder = os.getenv("SUBMISSIONS_FOLDER")

    for q in assignments:
        a = assignments.get(q)
        resp = session.get(
            f"https://www.gradescope.com/courses/{gs_course_id}/assignments/{a}/review_grades"
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        link = soup.find("a", class_="js-bulkExportModalDownload")
        if ".zip" in link["href"]:
            log.info("Downloading assignment: %s", q)
            resp = session.get("https://www.gradescope.com" + link["href"])
            q_no_colon = re.sub(r'[\\/:*?"<>|]', "", q)
            output_str = q_no_colon + ".zip"
            output_full = os.path.join(sub_folder, output_str)
            with open(output_full, "wb") as f:
                f.write(resp.content)
            log.info("Assignment %s downloaded!", q)
        else:
            log.info("Export not created yet; exporting assignment: %s", a)
            review_url = (
                f"https://www.gradescope.com/courses/{gs_course_id}/assignments/{a}/review_grades"
            )
            resp = session.get(review_url)

            soup = BeautifulSoup(resp.text, "html.parser")
            csrf = soup.find("meta", attrs={"name": "csrf-token"})["content"]

            session.headers["X-CSRF-Token"] = csrf

            resp = session.post(
                f"https://www.gradescope.com/courses/{gs_course_id}/assignments/{a}/export",
                headers={
                    "Referer": f"https://www.gradescope.com/courses/{gs_course_id}/assignments/{a}/review_grades"
                },
            )
            data = resp.json()
            file_id = data["generated_file_id"]

            url = (
                f"https://www.gradescope.com/courses/{gs_course_id}/generated_files/{file_id}.json"
            )

            # polling

            while True:
                resp = session.get(url)
                data = resp.json()
                progress = data["progress"]
                if progress == 1.0:
                    log.info("Export completed!")
                    break
                log.info("Waiting for export...(%s%% complete)", str(int(progress * 100)))
                time.sleep(1)

            url = f"https://www.gradescope.com/courses/{gs_course_id}/generated_files/{file_id}.zip"
            resp = session.get(url)
            q_no_colon = re.sub(r'[\\/:*?"<>|]', "", q)
            output_str = q_no_colon + ".zip"
            output_full = os.path.join(sub_folder, output_str)
            with open(output_full, "wb") as f:
                f.write(resp.content)
            log.info(f"Assignment {a} downloaded!")

    log.info("Download of class %s complete!", course_id)


def main():

    gs_downloader(253450)


if __name__ == "__main__":
    main()
