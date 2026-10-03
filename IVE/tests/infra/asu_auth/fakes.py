"""A stand-in for the Selenium Chrome driver, just deep enough for the login browser."""

from __future__ import annotations

from types import SimpleNamespace

from selenium.common.exceptions import NoSuchElementException, WebDriverException

CAS_LOGIN_URL = (
    "https://weblogin.asu.edu/cas/login?service=https%3A%2F%2Fcanvas.asu.edu%2Flogin%2Fcas"
)
DUO_URL = "https://api-ab654001.duosecurity.com/frame/v4/auth/prompt"
COURSE_URL = "https://canvas.asu.edu/courses/123456"


class FakeElement:
    def __init__(self, value: str = "") -> None:
        self.value = value
        self.typed: list[str] = []
        self.clicks = 0

    def get_attribute(self, name: str) -> str:
        return self.value if name == "value" else ""

    def send_keys(self, text: str) -> None:
        self.typed.append(text)

    def click(self) -> None:
        self.clicks += 1

    def is_displayed(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return True


class FakeDriver:
    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self.current_url = "about:blank"
        self.handles = ["tab-1"]
        self.current_window_handle = "tab-1"
        self.browser_cookies: list[dict] = []
        self.restored_cookies: list[dict] = []
        self.cdp_commands: list[str] = []
        self.elements: dict[tuple[str, str], list[FakeElement]] = {}
        self.rect = {"x": 10, "y": 10, "width": 1200, "height": 900}
        self.minimized = False
        self.quit_calls = 0
        self.page_load_timeout: float | None = None
        self.dead = False
        self.death_error: Exception = WebDriverException("invalid session id")
        self.switch_to = SimpleNamespace(window=self._switch_window)

    # -- what the tests poke ------------------------------------------------

    def kill(self, error: Exception | None = None) -> None:
        """The browser is gone; every call to it now fails with ``error``."""
        self.dead = True
        self.death_error = error or WebDriverException("invalid session id")

    def add_cas_form(self) -> tuple[FakeElement, FakeElement, FakeElement]:
        username, password, submit = FakeElement(), FakeElement(), FakeElement()
        self.elements[("id", "username")] = [username]
        self.elements[("id", "password")] = [password]
        self.elements[("css selector", "button[type='submit']")] = [submit]
        return username, password, submit

    def add_text_button(self, label: str) -> FakeElement:
        button = FakeElement()
        self.elements[("xpath", f"//*[contains(text(), '{label}')]")] = [button]
        return button

    # -- the driver surface the login browser uses --------------------------

    @property
    def window_handles(self) -> list[str]:
        if self.dead:
            raise self.death_error
        return list(self.handles)

    def _switch_window(self, handle: str) -> None:
        self.current_window_handle = handle

    def execute_cdp_cmd(self, command: str, params: dict) -> dict:
        if self.dead:
            raise self.death_error
        self.cdp_commands.append(command)
        if command == "Storage.getCookies":
            return {"cookies": list(self.browser_cookies)}
        if command == "Storage.setCookies":
            self.restored_cookies = list(params["cookies"])
            self.browser_cookies.extend(params["cookies"])
        if command == "Storage.clearCookies":
            self.browser_cookies = []
        return {}

    def find_element(self, by: str, value: str) -> FakeElement:
        found = self.elements.get((by, value))
        if not found:
            raise NoSuchElementException(f"{by}={value}")
        return found[0]

    def find_elements(self, by: str, value: str) -> list[FakeElement]:
        return list(self.elements.get((by, value), []))

    def get_window_rect(self) -> dict:
        return dict(self.rect)

    def set_page_load_timeout(self, seconds: float) -> None:
        self.page_load_timeout = seconds

    def minimize_window(self) -> None:
        self.minimized = True

    def set_window_rect(self, **rect: int) -> None:
        self.rect = dict(rect)
        self.minimized = False

    def quit(self) -> None:
        self.quit_calls += 1


class DriverFactory:
    """Hands out FakeDrivers and remembers every one it made."""

    def __init__(self) -> None:
        self.made: list[FakeDriver] = []

    def __call__(self, headless: bool) -> FakeDriver:
        driver = FakeDriver(headless)
        self.made.append(driver)
        return driver


def asu_cookie(name: str = "TGC", **extra) -> dict:
    return {"name": name, "value": "v", "domain": "weblogin.asu.edu", "path": "/cas", **extra}
