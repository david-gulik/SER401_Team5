"""
Adapters for fetching faculty roster CSVs from ASU's MyASU system.

Two implementations:
    - SeleniumRosterFetcher: Opens a browser for CAS + Duo MFA login,
      then transfers cookies to requests for efficient CSV downloads.
    - CookieFileRosterFetcher: Loads cookies from a Netscape-format
      cookie file for headless operation.
"""

from __future__ import annotations

import http.cookiejar
import logging
from dataclasses import dataclass

import requests

from GAVEL.app.dtos.roster import RosterRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MyASUEndpoints:
    """URL definitions for the MyASU roster system."""

    cas_login: str = "https://weblogin.asu.edu/cas/login"
    myasu_base: str = "https://webapp4.asu.edu/myasu"
    roster_path: str = "/faculty/roster"

    @property
    def roster_url(self) -> str:
        return f"{self.myasu_base}{self.roster_path}"


# ---------------------------------------------------------------------------
# Selenium-based roster fetcher
# ---------------------------------------------------------------------------


class SeleniumRosterFetcher:
    """
    Authenticates via Selenium (CAS + Duo MFA), then downloads
    roster CSVs using a requests.Session with transferred cookies.
    """

    def __init__(
        self,
        endpoints: MyASUEndpoints | None = None,
        mfa_timeout_seconds: int = 120,
        http_timeout: int = 30,
    ):
        self._endpoints = endpoints or MyASUEndpoints()
        self._mfa_timeout = mfa_timeout_seconds
        self._http_timeout = http_timeout
        self._session: requests.Session | None = None
        self._driver = None

    def authenticate(self) -> None:
        import time

        self._driver = self._create_driver()

        self._driver.get(f"{self._endpoints.myasu_base}/")

        print(
            f"[AUTH] Browser opened. Complete CAS login and Duo MFA.\n"
            f"[AUTH] Waiting up to {self._mfa_timeout}s..."
        )

        deadline = time.time() + self._mfa_timeout
        last_printed_url = ""
        authenticated = False
        myasu_domain = "webapp4.asu.edu"

        while time.time() < deadline:
            try:
                current = self._driver.current_url
            except Exception:
                break

            if current != last_printed_url:
                display = current[:120] + ("..." if len(current) > 120 else "")
                print(f"[AUTH] Current URL: {display}")
                last_printed_url = current

            if myasu_domain in current and "cas/login" not in current:
                time.sleep(3)
                try:
                    final_url = self._driver.current_url
                except Exception:
                    break

                if myasu_domain in final_url and "cas/login" not in final_url:
                    authenticated = True
                    break

            time.sleep(1)

        if not authenticated:
            try:
                last_url = self._driver.current_url
            except Exception:
                last_url = last_printed_url
            if self._driver:
                self._driver.quit()
                self._driver = None
            raise RuntimeError(f"Authentication timed out or browser closed.\nLast URL: {last_url}")

        logger.info("Authentication successful. Transferring session.")
        print("[AUTH] Authentication successful. Transferring cookies.")

        self._session = self._transfer_cookies(self._driver)
        self._driver.quit()
        self._driver = None

    def fetch_roster(self, request: RosterRequest) -> str:
        self._require_authenticated()
        params = {
            "term": request.term,
            "class": request.class_number,
            "format": "csv",
        }
        response = self._session.get(
            self._endpoints.roster_url,
            params=params,
            timeout=self._http_timeout,
        )
        self._check_response(response)
        return response.text

    def close(self) -> None:
        if self._driver:
            self._driver.quit()
            self._driver = None
        if self._session:
            self._session.close()
            self._session = None

    # -- Helpers ------------------------------------------------------------

    def _require_authenticated(self) -> None:
        if self._session is None:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

    @staticmethod
    def _create_driver():
        from selenium import webdriver

        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        return webdriver.Chrome(options=options)

    @staticmethod
    def _transfer_cookies(driver) -> requests.Session:
        session = requests.Session()
        for cookie in driver.get_cookies():
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )
        session.headers.update({"User-Agent": driver.execute_script("return navigator.userAgent")})
        return session

    @staticmethod
    def _check_response(response: requests.Response) -> None:
        if response.status_code != 200:
            raise RuntimeError(
                f"Roster fetch failed: HTTP {response.status_code}\nURL: {response.url}"
            )
        if "weblogin.asu.edu" in response.url:
            raise RuntimeError(
                "Session expired or invalid. Re-authentication required.\n"
                f"Redirected to: {response.url}"
            )
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type and "<html" in response.text[:500].lower():
            snippet = response.text[:1000]
            title = ""
            if "<title>" in snippet.lower():
                start = snippet.lower().index("<title>") + 7
                end = (
                    snippet.lower().index("</title>", start)
                    if "</title>" in snippet.lower()
                    else start + 100
                )
                title = snippet[start:end].strip()

            logger.debug("HTML response body (first 1000 chars): %s", snippet)
            raise RuntimeError(
                f"Received HTML instead of CSV.\n"
                f"Page title: {title or '(unknown)'}\n"
                f"URL: {response.url}\n"
                f"This may indicate insufficient permissions (faculty access required)\n"
                f"or an invalid term/class combination."
            )


# ---------------------------------------------------------------------------
# Cookie-file-based roster fetcher
# ---------------------------------------------------------------------------


class CookieFileRosterFetcher:
    """
    Loads cookies from a Netscape-format cookie file and uses them
    to download roster CSVs without Selenium.
    """

    def __init__(
        self,
        cookie_file_path: str,
        endpoints: MyASUEndpoints | None = None,
        http_timeout: int = 30,
    ):
        self._cookie_path = cookie_file_path
        self._endpoints = endpoints or MyASUEndpoints()
        self._http_timeout = http_timeout
        self._session: requests.Session | None = None

    def authenticate(self) -> None:
        jar = http.cookiejar.MozillaCookieJar(self._cookie_path)
        jar.load(ignore_discard=True, ignore_expires=True)

        self._session = requests.Session()
        self._session.cookies = jar
        self._session.headers.update(
            {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")}
        )
        logger.info("Loaded %d cookies from %s", len(jar), self._cookie_path)

    def fetch_roster(self, request: RosterRequest) -> str:
        if self._session is None:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        params = {
            "term": request.term,
            "class": request.class_number,
            "format": "csv",
        }
        response = self._session.get(
            self._endpoints.roster_url,
            params=params,
            timeout=self._http_timeout,
        )
        SeleniumRosterFetcher._check_response(response)
        return response.text

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None
