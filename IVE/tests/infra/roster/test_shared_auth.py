"""Roster login through the shared browser: what it reads, and what it leaves running."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from selenium.common.exceptions import TimeoutException

from GAVEL.infra.roster import shared_auth
from GAVEL.infra.roster.shared_auth import SharedAuthProvider
from GAVEL.services.config_service import RosterConfig

TOKEN_KEY = "catalog.jwt.token"
NEW_TOKEN = "new-catalog-token-0123456789"
STALE_TOKEN = "stale-catalog-token-0123456789"

FAVICON_URL = "https://catalog.apps.asu.edu/favicon.ico"
# What the browser shows while signed out: the CAS page, whose address names
# the catalog site it will return to.
CAS_URL = (
    "https://weblogin.asu.edu/cas/login?service=https%3A%2F%2Fweblogin.asu.edu%2Fserviceauth"
    "%2Foauth2%2Fnative%2Fallow%3Fredirect_uri%3Dhttps%253A%252F%252Fcatalog.apps.asu.edu"
)
DUO_URL = "https://api-ab654001.duosecurity.com/frame/v4/auth/prompt"
BACK_ON_CATALOG_URL = "https://catalog.apps.asu.edu/catalog?code=abc&state=xyz"
MYASU_URL = "https://webapp4.asu.edu/myasu/"


class ScriptedDriver:
    """Plays back the pages a browser passes through for the roster login."""

    def __init__(self, login_pages: list[str]) -> None:
        self._login_pages = login_pages  # shown after the allow URL, before the catalog
        self._pending: list[str] = []
        self._url = "about:blank"
        self.last_seen = self._url  # the page the caller last looked at
        self.visited: list[str] = []
        self.storage: dict[str, str] = {}
        self._exchanging = False
        self.never_finishes_loading = False
        self.storage_at_login: list[dict[str, str]] = []

    def get(self, url: str) -> None:
        self.visited.append(url)
        if self.never_finishes_loading and "/oauth2/" in url:
            raise TimeoutException("timeout: Timed out receiving message from renderer")
        if "/oauth2/" in url:
            self.storage_at_login.append(dict(self.storage))
            self._pending = [*self._login_pages, BACK_ON_CATALOG_URL]
            self._url = self._pending.pop(0)
        else:
            self._url = url

    @property
    def current_url(self) -> str:
        url = self._url
        if url == BACK_ON_CATALOG_URL and TOKEN_KEY not in self.storage:
            self._exchanging = True
        if self._pending:
            self._url = self._pending.pop(0)
        self.last_seen = url
        return url

    def execute_script(self, script: str):
        if script == "sessionStorage.clear();":
            self.storage.clear()
            return None
        if script.startswith("sessionStorage.removeItem"):
            self.storage.pop(script.split("'")[1], None)
            return None
        if script.startswith("sessionStorage.setItem"):
            _, key, _, value, _ = script.split("'")
            self.storage[key] = value
            return None
        if script.startswith("return sessionStorage.getItem"):
            key = script.split("'")[1]
            if key == TOKEN_KEY and self._exchanging:
                # The page needs a moment to trade its code for a token.
                self._exchanging = False
                found = self.storage.get(key)
                self.storage[key] = NEW_TOKEN
                return found
            return self.storage.get(key)
        if "navigator.userAgent" in script:
            return "FakeBrowser/1.0"
        raise AssertionError(f"unexpected script: {script}")

    def get_cookies(self) -> list[dict]:
        if self._url.startswith(MYASU_URL):
            return [{"name": "JSESSIONID", "value": "roster", "domain": "webapp4.asu.edu"}]
        return [{"name": "catalog", "value": "c", "domain": "catalog.apps.asu.edu"}]


class FakeBrowser:
    def __init__(self, driver: ScriptedDriver, is_open: bool = False) -> None:
        self.driver = driver
        self.is_open = is_open
        self.has_credentials = True
        self.uses: list[dict] = []
        self.assisted_on: list[str] = []
        self.close_calls = 0

    @contextmanager
    def use(self, *, headless: bool = False, show: bool = True):
        self.uses.append({"headless": headless, "show": show})
        self.is_open = True
        yield self.driver

    def assist_login(self, driver, credentials=None) -> None:
        self.assisted_on.append(driver.last_seen)

    def close(self) -> None:
        self.close_calls += 1


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    monkeypatch.setattr(shared_auth.time, "sleep", lambda seconds: None)


def make_provider(driver: ScriptedDriver, is_open: bool = False):
    browser = FakeBrowser(driver, is_open=is_open)
    provider = SharedAuthProvider(RosterConfig(auth_method="selenium"), browser)
    return provider, browser


def test_login_yields_a_token_and_myasu_cookies() -> None:
    driver = ScriptedDriver(login_pages=[CAS_URL, DUO_URL])
    provider, browser = make_provider(driver)

    try:
        session = provider.get_roster_session()

        assert provider.obtain_token() == NEW_TOKEN
        assert session.cookies.get("JSESSIONID") == "roster"
        assert session.headers["User-Agent"] == "FakeBrowser/1.0"
        assert len(browser.uses) == 1
    finally:
        provider.close()


def test_sign_in_page_is_not_mistaken_for_the_catalog() -> None:
    """The login is helped along on every page until the catalog is really reached."""
    driver = ScriptedDriver(login_pages=[CAS_URL, CAS_URL, DUO_URL])
    provider, browser = make_provider(driver)

    try:
        assert provider.obtain_token() == NEW_TOKEN
    finally:
        provider.close()

    assert browser.assisted_on.count(CAS_URL) == 2
    assert DUO_URL in browser.assisted_on


def test_token_left_in_the_tab_by_an_earlier_login_is_not_reused() -> None:
    driver = ScriptedDriver(login_pages=[])
    driver.storage[TOKEN_KEY] = STALE_TOKEN
    provider, _ = make_provider(driver)

    try:
        assert provider.obtain_token() == NEW_TOKEN
    finally:
        provider.close()


LEFT_BY_THE_CATALOG_PAGE = {
    TOKEN_KEY: STALE_TOKEN,
    "catalog.ss.name": "Bailey",
    "catalog.jwt.refresh.token": "refresh",
    "catalog.jwt.expiration": "Wed Sep 30 2026 18:53:00",
}
PKCE_KEYS = {"catalog.serviceauth.codeVerifier", "catalog.serviceauth.state"}


def test_full_login_starts_from_an_empty_catalog_tab() -> None:
    """Leftover user details make the catalog page discard its token and redirect forever."""
    driver = ScriptedDriver(login_pages=[])
    driver.storage.update(LEFT_BY_THE_CATALOG_PAGE)
    provider, _ = make_provider(driver)

    try:
        provider.ensure_authenticated()
    finally:
        provider.close()

    assert set(driver.storage_at_login[0]) == PKCE_KEYS


def test_quiet_refresh_starts_from_an_empty_catalog_tab() -> None:
    driver = ScriptedDriver(login_pages=[])
    provider, _ = make_provider(driver)
    provider.ensure_authenticated()
    provider.close()
    driver.storage.update(LEFT_BY_THE_CATALOG_PAGE)

    try:
        provider.ensure_authenticated()
    finally:
        provider.close()

    assert any("/passive/" in url for url in driver.visited)
    assert set(driver.storage_at_login[-1]) == PKCE_KEYS


def test_a_page_that_never_finishes_loading_is_reported_plainly() -> None:
    driver = ScriptedDriver(login_pages=[])
    driver.never_finishes_loading = True
    provider, _ = make_provider(driver)

    with pytest.raises(RuntimeError, match="did not finish loading"):
        provider.ensure_authenticated()

    assert provider.is_valid is False


def test_close_releases_the_roster_session_but_not_the_browser() -> None:
    driver = ScriptedDriver(login_pages=[])
    provider, browser = make_provider(driver)
    provider.ensure_authenticated()

    provider.close()

    assert browser.close_calls == 0
    assert provider.is_valid is False


def test_next_download_refreshes_quietly_in_the_open_browser() -> None:
    driver = ScriptedDriver(login_pages=[])
    provider, browser = make_provider(driver)
    provider.ensure_authenticated()
    provider.close()

    try:
        session = provider.get_roster_session()

        # Window stays out of the way, and the cookies still come from MyASU.
        assert browser.uses[-1]["show"] is False
        assert any("/passive/" in url for url in driver.visited)
        assert session.cookies.get("JSESSIONID") == "roster"
        assert provider.is_valid is True
    finally:
        provider.close()


def test_a_failed_quiet_refresh_falls_back_to_the_full_login(monkeypatch) -> None:
    driver = ScriptedDriver(login_pages=[CAS_URL])
    provider, browser = make_provider(driver)
    provider.ensure_authenticated()
    provider.close()
    monkeypatch.setattr(provider, "_try_silent_refresh", lambda: False)

    try:
        assert provider.obtain_token() == NEW_TOKEN
    finally:
        provider.close()

    assert browser.uses == [{"headless": False, "show": True}] * 2


def test_first_login_skips_the_quiet_refresh_even_if_the_browser_is_already_open() -> None:
    """Another download may have opened the browser; that says nothing about being signed in."""
    driver = ScriptedDriver(login_pages=[CAS_URL])
    provider, browser = make_provider(driver, is_open=True)

    try:
        assert provider.obtain_token() == NEW_TOKEN
    finally:
        provider.close()

    assert not any("/passive/" in url for url in driver.visited)
    assert browser.uses == [{"headless": False, "show": True}]
