"""Reaching Gradescope through Canvas in a browser that other downloads also use."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from selenium.common.exceptions import NoSuchElementException

from GAVEL.infra.gradescope import http_gradescope_client as module
from GAVEL.infra.gradescope.http_gradescope_client import http_gradescope_client

COURSE_URL = "https://canvas.asu.edu/courses/123456"
GRADESCOPE_URL = "https://www.gradescope.com/courses/987654"


class FakeElement:
    def __init__(self, on_click=None) -> None:
        self._on_click = on_click

    def is_displayed(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return True

    def click(self) -> None:
        if self._on_click:
            self._on_click()


class CanvasDriver:
    """One Canvas tab whose Gradescope link opens Gradescope in a second tab."""

    def __init__(self) -> None:
        self.urls = {"home": "about:blank"}
        self.current_window_handle = "home"
        self.switch_to = SimpleNamespace(window=self._switch)
        self.closed: list[str] = []

    @property
    def window_handles(self) -> list[str]:
        return list(self.urls)

    @property
    def current_url(self) -> str:
        return self.urls[self.current_window_handle]

    def _switch(self, handle: str) -> None:
        self.current_window_handle = handle

    def get(self, url: str) -> None:
        self.urls[self.current_window_handle] = url

    def close(self) -> None:
        self.closed.append(self.current_window_handle)
        del self.urls[self.current_window_handle]

    def _open_gradescope(self) -> None:
        self.urls["gradescope"] = GRADESCOPE_URL

    def find_element(self, by: str, value: str) -> FakeElement:
        on_course = self.current_url == COURSE_URL
        if on_course and (by, value) == ("id", "section-tabs"):
            return FakeElement()
        if on_course and by == "xpath" and "Gradescope" in value:
            return FakeElement(on_click=self._open_gradescope)
        raise NoSuchElementException(f"{by}={value}")

    def find_elements(self, by: str, value: str) -> list[FakeElement]:
        try:
            return [self.find_element(by, value)]
        except NoSuchElementException:
            return []

    def get_cookies(self) -> list[dict]:
        if self.current_window_handle == "gradescope":
            return [
                {"name": "_gradescope_session", "value": "gs-session"},
                {"name": "token", "value": "gs-token"},
            ]
        return [{"name": "canvas_session", "value": "canvas"}]


class FakeBrowser:
    def __init__(self) -> None:
        self.driver = CanvasDriver()
        self.uses: list[bool] = []
        self.logins: list[dict] = []
        self.close_calls = 0

    @contextmanager
    def use(self, *, headless: bool = False, show: bool = True):
        self.uses.append(headless)
        yield self.driver

    def wait_for_login(self, driver, arrived, *, credentials=None, timeout=None) -> None:
        self.logins.append({"credentials": credentials, "arrived": arrived(driver)})

    def close(self) -> None:
        self.close_calls += 1


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)


def test_session_and_course_id_come_from_the_gradescope_tab() -> None:
    browser = FakeBrowser()
    client = http_gradescope_client(COURSE_URL, headless=True, browser=browser)

    session, course_id = client.capture_session("asurite", "secret", timeout=1)

    assert course_id == "987654"
    assert session.session_cookie == "gs-session"
    assert session.token == "gs-token"
    assert browser.uses == [True]
    assert browser.logins == [{"credentials": ("asurite", "secret"), "arrived": True}]


def test_shared_browser_is_left_open_with_only_its_original_tab() -> None:
    browser = FakeBrowser()
    client = http_gradescope_client(COURSE_URL, browser=browser)

    client.capture_session("asurite", "secret", timeout=1)

    assert browser.close_calls == 0
    assert browser.driver.closed == ["gradescope"]
    assert browser.driver.window_handles == ["home"]
    assert browser.driver.current_window_handle == "home"


def test_a_second_capture_works_in_the_same_browser() -> None:
    browser = FakeBrowser()
    client = http_gradescope_client(COURSE_URL, browser=browser)

    client.capture_session("asurite", "secret", timeout=1)
    _, course_id = client.capture_session("asurite", "secret", timeout=1)

    assert course_id == "987654"
    assert browser.driver.window_handles == ["home"]


def test_tabs_are_tidied_even_when_gradescope_is_never_reached(monkeypatch) -> None:
    browser = FakeBrowser()
    client = http_gradescope_client(COURSE_URL, browser=browser)
    # The link opens a tab that never gets to Gradescope.
    monkeypatch.setattr(
        browser.driver,
        "_open_gradescope",
        lambda: browser.driver.urls.update(gradescope="https://canvas.asu.edu/error"),
    )

    with pytest.raises(RuntimeError, match="Timed out during SSO flow"):
        client.capture_session("asurite", "secret", timeout=0.2)

    assert browser.driver.window_handles == ["home"]
    assert browser.close_calls == 0


def test_without_a_shared_browser_a_private_one_is_opened_and_closed(monkeypatch) -> None:
    private = FakeBrowser()
    monkeypatch.setattr(module, "AsuBrowserSession", lambda: private)
    client = http_gradescope_client(COURSE_URL)

    _, course_id = client.capture_session("asurite", "secret", timeout=1)

    assert course_id == "987654"
    assert private.close_calls == 1
