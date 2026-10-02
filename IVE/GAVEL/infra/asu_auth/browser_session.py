"""One Chrome browser shared by every feature that needs an ASU login.

The roster download and the Gradescope download both have to get through ASU
single sign-on (CAS) and Duo before they can do anything. Each used to start
its own throwaway browser, so each one asked for Duo again. This module owns
a single browser for the life of the app instead:

* The first feature to need a login performs it; later ones find the browser
  already signed in.
* When the app is allowed to remember the login, the browser's cookies are
  saved at the end of every use and restored into the next browser that is
  started, so a later run of the app can skip the login as well.

Nothing here decides whether a saved login is still good. The cookies are put
back, the caller navigates where it needs to go, and the page the browser
lands on answers the question: a stale or missing login simply shows the
sign-in page and the normal login takes over.
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse

import urllib3
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from GAVEL.infra.asu_auth.cookie_store import CookieStore, restorable

logger = logging.getLogger(__name__)

CAS_HOST = "weblogin.asu.edu"
DUO_DOMAIN = "duosecurity.com"

# Duo asks "Is this your device?" after the second factor is approved.
DUO_TRUST_THIS_BROWSER = "Yes, this is my device"
DUO_DO_NOT_TRUST = "No, other people use this device"

Credentials = tuple[str, str]

# A browser that has gone away fails in more than one way: Selenium raises its
# own errors while the driver process is still running, and the HTTP client
# underneath raises once that process is gone as well.
BROWSER_ERRORS = (WebDriverException, urllib3.exceptions.HTTPError, OSError)


class AsuLoginError(RuntimeError):
    """The ASU login did not finish."""


def env_credentials() -> Credentials | None:
    """CANVAS_USERNAME / CANVAS_PASSWORD from the environment, when both are set."""
    username = os.getenv("CANVAS_USERNAME")
    password = os.getenv("CANVAS_PASSWORD")
    if username and password:
        return username, password
    return None


def create_chrome_driver(headless: bool) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(options=options)


def host_of(url: str) -> str:
    """Host name of a URL, lower-cased; empty when there is none.

    Compare hosts rather than searching the whole URL: the sign-in page's
    address carries the destination site inside its query string.
    """
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def on_login_page(url: str) -> bool:
    """True while the browser is on the CAS sign-in page or a Duo page."""
    host = host_of(url)
    return host == CAS_HOST or host == DUO_DOMAIN or host.endswith(f".{DUO_DOMAIN}")


class AsuBrowserSession:
    """A lazily started Chrome browser that stays signed in to ASU.

    Borrow the browser with :meth:`use`; only one caller holds it at a time.
    The browser is started on first use, kept open between uses, and closed by
    :meth:`close` (also registered to run when the interpreter exits).

    Passing a ``cookie_store`` means the login may be remembered: cookies are
    saved to it and Duo is told this is the user's own device. Without one,
    nothing is written to disk and Duo is told the device is shared, so the
    login lasts only as long as this browser stays open.
    """

    def __init__(
        self,
        cookie_store: CookieStore | None = None,
        *,
        mfa_timeout: int = 120,
        driver_factory: Callable[[bool], Any] = create_chrome_driver,
        credentials: Callable[[], Credentials | None] = env_credentials,
        poll_interval: float = 1.0,
        page_load_timeout: int = 60,
    ) -> None:
        self._store = cookie_store
        self._mfa_timeout = mfa_timeout
        self._driver_factory = driver_factory
        self._credentials = credentials
        self._poll_interval = poll_interval
        self._page_load_timeout = page_load_timeout

        self._lock = threading.RLock()
        self._driver: Any = None
        self._headless = False
        self._hidden_rect: dict | None = None  # window position while minimized
        self._carried: list[dict] = []  # last cookies seen, for restarts without a store
        self._autofill_spent = False
        self._exit_hook_registered = False

    # -- Public API ---------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._driver is not None

    @property
    def remembers_login(self) -> bool:
        return self._store is not None

    @property
    def has_credentials(self) -> bool:
        return self._credentials() is not None

    @property
    def mfa_timeout(self) -> int:
        return self._mfa_timeout

    @contextmanager
    def use(self, *, headless: bool = False, show: bool = True) -> Iterator[Any]:
        """Borrow the browser for one piece of work.

        Starts the browser if it is not running (or was closed by the user),
        brings its window back when ``show`` is true, and on the way out saves
        the cookies and minimizes the window. ``headless`` only matters when a
        browser has to be started; a visible browser is never swapped for a
        hidden one, but a hidden one is reopened visibly when asked.
        """
        with self._lock:
            driver = self._ready_driver(headless)
            self._autofill_spent = False
            if show:
                self._show()
            try:
                yield driver
            finally:
                self._save_cookies()
                self._hide()

    def wait_for_login(
        self,
        driver: Any,
        arrived: Callable[[Any], bool],
        *,
        credentials: Credentials | None = None,
        timeout: float | None = None,
    ) -> None:
        """Block until ``arrived(driver)`` is true, helping the login along meanwhile.

        Call this right after navigating somewhere that needs an ASU login.
        If the browser is already signed in, ``arrived`` is true straight away
        and nothing else happens. Otherwise the sign-in form is filled once
        from the saved credentials and Duo's device question is answered, and
        the user completes whatever is left (typically approving the Duo
        prompt) in the browser.
        """
        limit = self._mfa_timeout if timeout is None else timeout
        deadline = time.monotonic() + limit
        last_url = ""
        while True:
            try:
                last_url = driver.current_url
            except BROWSER_ERRORS as exc:
                raise AsuLoginError(
                    "The login browser was closed before the ASU login finished."
                ) from exc

            if not on_login_page(last_url) and self._has_arrived(driver, arrived):
                return
            self.assist_login(driver, credentials)

            if time.monotonic() >= deadline:
                break
            time.sleep(self._poll_interval)

        raise AsuLoginError(
            f"Timed out after {int(limit)}s waiting for the ASU login to finish.\n"
            f"Last page: {last_url}\n"
            "Complete the CAS login and approve the Duo prompt in the browser. If the "
            "page is still the sign-in form, check CANVAS_USERNAME and CANVAS_PASSWORD."
        )

    def assist_login(self, driver: Any, credentials: Credentials | None = None) -> None:
        """Do whatever the current page needs to move a login forward, if anything.

        Safe to call on any page, as often as needed: it fills the CAS sign-in
        form (once per :meth:`use`) and answers Duo's device question.
        """
        try:
            url = driver.current_url
        except BROWSER_ERRORS:
            return
        if host_of(url) == CAS_HOST:
            self._fill_cas_form(driver, credentials or self._credentials())
        else:
            self._answer_duo_device_question(driver)

    def forget(self) -> bool:
        """Delete the saved login and sign the running browser out.

        Returns True when a saved login existed on disk.
        """
        with self._lock:
            self._carried = []
            removed = self._store.clear() if self._store is not None else False
            if self._driver is not None:
                try:
                    self._driver.execute_cdp_cmd("Storage.clearCookies", {})
                except BROWSER_ERRORS as exc:
                    logger.debug("Could not clear browser cookies: %s", exc)
            return removed

    def close(self) -> None:
        """Save the cookies and quit the browser. Safe to call more than once."""
        # A download may still hold the browser when the app is closing; do not
        # wait on it forever, just skip the final save.
        locked = self._lock.acquire(timeout=5)
        try:
            if self._driver is None:
                return
            if locked:
                self._save_cookies()
            self._discard_driver()
        finally:
            if locked:
                self._lock.release()

    # -- Browser lifecycle --------------------------------------------------

    def _ready_driver(self, headless: bool) -> Any:
        if self._driver is not None and not self._responsive():
            logger.info("Login browser is gone; starting a new one.")
            self._discard_driver()
        if self._driver is not None and self._headless and not headless:
            # A hidden browser cannot show a login page to the user.
            self._save_cookies()
            self._discard_driver()
        if self._driver is None:
            self._start(headless)
        return self._driver

    def _responsive(self) -> bool:
        """True when the browser still answers and has a window to work in."""
        try:
            handles = self._driver.window_handles
            if not handles:
                return False
            try:
                current = self._driver.current_window_handle
            except BROWSER_ERRORS:
                current = None
            if current not in handles:
                self._driver.switch_to.window(handles[0])
            return True
        except BROWSER_ERRORS:
            return False

    def _start(self, headless: bool) -> None:
        logger.info("Starting login browser (headless=%s).", headless)
        self._driver = self._driver_factory(headless)
        self._headless = headless
        self._hidden_rect = None

        # A page that keeps redirecting never finishes loading. Without a
        # limit, a navigation would wait on it for minutes instead of failing.
        try:
            self._driver.set_page_load_timeout(self._page_load_timeout)
        except BROWSER_ERRORS as exc:
            logger.debug("Could not set the page load limit: %s", exc)

        if not self._exit_hook_registered:
            atexit.register(self.close)
            self._exit_hook_registered = True

        cookies = self._store.load() if self._store is not None else self._carried
        if not cookies:
            return
        try:
            self._driver.execute_cdp_cmd("Storage.setCookies", {"cookies": cookies})
            logger.info("Restored %d saved login cookies.", len(cookies))
        except BROWSER_ERRORS as exc:
            # Not fatal: the browser just starts signed out.
            logger.warning("Could not restore the saved login: %s", exc)

    def _discard_driver(self) -> None:
        driver, self._driver = self._driver, None
        self._hidden_rect = None
        if driver is None:
            return
        try:
            driver.quit()
        except Exception as exc:  # noqa: BLE001 - quitting a dead browser can fail any way
            logger.debug("Error while closing the login browser: %s", exc)

    def _save_cookies(self) -> None:
        if self._driver is None:
            return
        try:
            result = self._driver.execute_cdp_cmd("Storage.getCookies", {})
        except BROWSER_ERRORS as exc:
            logger.debug("Could not read browser cookies: %s", exc)
            return
        cookies = result.get("cookies") if isinstance(result, dict) else None
        if not isinstance(cookies, list):
            return
        self._carried = restorable(cookies)
        if self._store is None:
            return
        try:
            self._store.save(cookies)
        except OSError as exc:
            logger.warning("Could not save the login to %s: %s", self._store.path, exc)

    # -- Window -------------------------------------------------------------

    def _show(self) -> None:
        if self._headless or self._hidden_rect is None:
            return
        rect, self._hidden_rect = self._hidden_rect, None
        try:
            self._driver.set_window_rect(**rect)
        except BROWSER_ERRORS as exc:
            logger.debug("Could not restore the browser window: %s", exc)

    def _hide(self) -> None:
        if self._driver is None or self._headless:
            return
        try:
            rect = self._driver.get_window_rect()
            self._driver.minimize_window()
        except BROWSER_ERRORS as exc:
            logger.debug("Could not minimize the browser window: %s", exc)
            return
        if isinstance(rect, dict):
            self._hidden_rect = {k: rect[k] for k in ("x", "y", "width", "height") if k in rect}

    # -- Login pages --------------------------------------------------------

    @staticmethod
    def _has_arrived(driver: Any, arrived: Callable[[Any], bool]) -> bool:
        try:
            return bool(arrived(driver))
        except BROWSER_ERRORS:
            # The page is mid-navigation; ask again on the next pass.
            return False

    def _fill_cas_form(self, driver: Any, credentials: Credentials | None) -> bool:
        """Submit the CAS sign-in form with the saved credentials, at most once per use.

        Once only: if CAS rejects the credentials it shows the empty form
        again, and submitting the same wrong password repeatedly could lock
        the account. After the first attempt the form is left for the user.
        """
        if credentials is None or self._autofill_spent:
            return False
        try:
            user_field = driver.find_element(By.ID, "username")
            pass_field = driver.find_element(By.ID, "password")
            if user_field.get_attribute("value"):
                return False
            user_field.send_keys(credentials[0])
            pass_field.send_keys(credentials[1])
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        except BROWSER_ERRORS as exc:
            logger.debug("CAS sign-in form not ready: %s", exc)
            return False
        self._autofill_spent = True
        logger.info("Filled the CAS sign-in form from saved credentials.")
        return True

    def _answer_duo_device_question(self, driver: Any) -> bool:
        """Answer Duo's "Is this your device?" page when it is showing.

        "Yes" lets Duo remember this browser, which only helps when its
        cookies are kept; otherwise the device is reported as shared.
        """
        label = DUO_TRUST_THIS_BROWSER if self.remembers_login else DUO_DO_NOT_TRUST
        try:
            buttons = driver.find_elements(By.XPATH, f"//*[contains(text(), '{label}')]")
            if not buttons:
                return False
            buttons[0].click()
        except BROWSER_ERRORS:
            return False
        logger.info("Answered Duo's device question: %s.", label)
        return True
