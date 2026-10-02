"""The shared login browser: one browser, one login, remembered between runs."""

from __future__ import annotations

from pathlib import Path

import pytest
import urllib3
from selenium.common.exceptions import WebDriverException

from GAVEL.infra.asu_auth.browser_session import (
    DUO_DO_NOT_TRUST,
    DUO_TRUST_THIS_BROWSER,
    AsuBrowserSession,
    AsuLoginError,
    host_of,
    on_login_page,
)
from GAVEL.infra.asu_auth.cookie_store import CookieStore
from tests.infra.asu_auth.fakes import (
    CAS_LOGIN_URL,
    COURSE_URL,
    DUO_URL,
    DriverFactory,
    asu_cookie,
)


@pytest.fixture
def factory() -> DriverFactory:
    return DriverFactory()


@pytest.fixture
def store(tmp_path: Path) -> CookieStore:
    return CookieStore(tmp_path / "asu_login_cookies.json")


def make_session(factory, store=None, credentials=("asurite", "secret")) -> AsuBrowserSession:
    return AsuBrowserSession(
        store,
        driver_factory=factory,
        credentials=lambda: credentials,
        poll_interval=0,
    )


class TestOneBrowser:
    def test_nothing_is_started_until_first_use(self, factory) -> None:
        session = make_session(factory)

        assert factory.made == []
        assert session.is_open is False

    def test_page_loads_are_given_a_time_limit(self, factory) -> None:
        """A page stuck in a redirect loop must fail, not hang the download."""
        session = AsuBrowserSession(driver_factory=factory, page_load_timeout=45)

        with session.use() as driver:
            assert driver.page_load_timeout == 45

    def test_every_use_gets_the_same_browser(self, factory) -> None:
        session = make_session(factory)

        with session.use() as first:
            pass
        with session.use() as second:
            pass

        assert first is second
        assert len(factory.made) == 1
        assert first.quit_calls == 0

    @pytest.mark.parametrize(
        "failure",
        [
            WebDriverException("invalid session id"),  # window closed, driver still running
            ConnectionRefusedError("driver process has exited"),
            urllib3.exceptions.MaxRetryError(None, "/session", "driver process has exited"),
        ],
        ids=["window-closed", "driver-exited", "driver-unreachable"],
    )
    def test_a_browser_that_went_away_is_replaced_and_signed_back_in(
        self, factory, failure
    ) -> None:
        session = make_session(factory)
        with session.use() as first:
            first.browser_cookies = [asu_cookie()]
        first.kill(failure)

        with session.use() as second:
            pass

        assert second is not first
        assert [c["name"] for c in second.restored_cookies] == ["TGC"]

    def test_a_hidden_browser_is_reopened_visibly_keeping_the_login(self, factory) -> None:
        session = make_session(factory)
        with session.use(headless=True) as hidden:
            hidden.browser_cookies = [asu_cookie()]

        with session.use(headless=False) as visible:
            pass

        assert hidden.quit_calls == 1
        assert visible.headless is False
        assert [c["name"] for c in visible.restored_cookies] == ["TGC"]

    def test_a_visible_browser_is_kept_when_a_hidden_one_is_asked_for(self, factory) -> None:
        session = make_session(factory)
        with session.use(headless=False) as visible:
            pass

        with session.use(headless=True) as again:
            pass

        assert again is visible

    def test_window_is_minimized_between_uses_and_brought_back(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:
            assert driver.minimized is False
        assert driver.minimized is True

        with session.use():
            assert driver.minimized is False

    def test_window_stays_minimized_for_background_work(self, factory) -> None:
        session = make_session(factory)
        with session.use():
            pass

        with session.use(show=False) as driver:
            assert driver.minimized is True

    def test_close_quits_the_browser_once(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:
            pass

        session.close()
        session.close()

        assert driver.quit_calls == 1
        assert session.is_open is False

    def test_close_copes_with_a_browser_that_already_went_away(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:
            pass
        driver.kill(ConnectionRefusedError("driver process has exited"))

        session.close()

        assert session.is_open is False


class TestRememberingTheLogin:
    def test_cookies_are_saved_when_a_use_ends(self, factory, store) -> None:
        session = make_session(factory, store)

        with session.use() as driver:
            driver.browser_cookies = [asu_cookie(), asu_cookie("NID", domain=".google.com")]

        assert [c["name"] for c in store.load()] == ["TGC"]

    def test_saved_cookies_go_into_the_next_browser(self, factory, store) -> None:
        store.save([asu_cookie()])
        session = make_session(factory, store)

        with session.use() as driver:
            assert [c["name"] for c in driver.restored_cookies] == ["TGC"]

    def test_a_failed_restore_still_gives_a_working_browser(self, factory, store) -> None:
        store.save([asu_cookie()])

        def flaky_factory(headless: bool):
            driver = factory(headless)
            original = driver.execute_cdp_cmd

            def execute(command, params):
                if command == "Storage.setCookies":
                    raise WebDriverException("cookie rejected")
                return original(command, params)

            driver.execute_cdp_cmd = execute
            return driver

        session = AsuBrowserSession(store, driver_factory=flaky_factory, poll_interval=0)

        with session.use() as driver:
            assert driver.restored_cookies == []

    def test_without_a_store_nothing_is_written(self, factory, tmp_path) -> None:
        session = make_session(factory)

        with session.use() as driver:
            driver.browser_cookies = [asu_cookie()]
        session.close()

        assert list(tmp_path.iterdir()) == []
        assert session.remembers_login is False

    def test_forget_deletes_the_file_and_signs_the_browser_out(self, factory, store) -> None:
        session = make_session(factory, store)
        with session.use() as driver:
            driver.browser_cookies = [asu_cookie()]

        assert session.forget() is True

        assert not store.path.exists()
        assert driver.browser_cookies == []
        assert session.forget() is False


class TestLoginPages:
    def test_already_signed_in_returns_at_once_and_touches_nothing(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:
            driver.current_url = COURSE_URL
            username, _, submit = driver.add_cas_form()

            session.wait_for_login(driver, lambda d: True)

        assert username.typed == []
        assert submit.clicks == 0

    def test_sign_in_page_is_never_mistaken_for_the_destination(self, factory) -> None:
        """The CAS address carries the destination site in its query string."""
        session = make_session(factory)
        with session.use() as driver:
            driver.current_url = CAS_LOGIN_URL

            with pytest.raises(AsuLoginError, match="Timed out"):
                session.wait_for_login(
                    driver, lambda d: "canvas.asu.edu" in d.current_url, timeout=0
                )

    def test_cas_form_is_filled_from_saved_credentials(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:
            driver.current_url = CAS_LOGIN_URL
            username, password, submit = driver.add_cas_form()

            session.assist_login(driver)

        assert username.typed == ["asurite"]
        assert password.typed == ["secret"]
        assert submit.clicks == 1

    def test_cas_form_is_filled_only_once_per_use(self, factory) -> None:
        """A rejected password must not be resubmitted over and over."""
        session = make_session(factory)
        with session.use() as driver:
            driver.current_url = CAS_LOGIN_URL
            _, _, submit = driver.add_cas_form()

            session.assist_login(driver)
            session.assist_login(driver)
            session.assist_login(driver)

        assert submit.clicks == 1

    def test_cas_form_can_be_filled_again_in_a_later_use(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:
            driver.current_url = CAS_LOGIN_URL
            _, _, submit = driver.add_cas_form()
            session.assist_login(driver)

        with session.use():
            session.assist_login(driver)

        assert submit.clicks == 2

    def test_cas_form_is_left_alone_without_credentials(self, factory) -> None:
        session = make_session(factory, credentials=None)
        with session.use() as driver:
            driver.current_url = CAS_LOGIN_URL
            username, _, submit = driver.add_cas_form()

            session.assist_login(driver)

        assert username.typed == []
        assert submit.clicks == 0
        assert session.has_credentials is False

    def test_credentials_passed_in_win_over_the_saved_ones(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:
            driver.current_url = CAS_LOGIN_URL
            username, _, _ = driver.add_cas_form()

            session.assist_login(driver, ("other", "pw"))

        assert username.typed == ["other"]

    def test_duo_is_told_this_is_my_device_when_the_login_is_remembered(
        self, factory, store
    ) -> None:
        session = make_session(factory, store)
        with session.use() as driver:
            driver.current_url = DUO_URL
            yes = driver.add_text_button(DUO_TRUST_THIS_BROWSER)
            no = driver.add_text_button(DUO_DO_NOT_TRUST)

            session.assist_login(driver)

        assert (yes.clicks, no.clicks) == (1, 0)

    def test_duo_is_told_the_device_is_shared_when_nothing_is_remembered(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:
            driver.current_url = DUO_URL
            yes = driver.add_text_button(DUO_TRUST_THIS_BROWSER)
            no = driver.add_text_button(DUO_DO_NOT_TRUST)

            session.assist_login(driver)

        assert (yes.clicks, no.clicks) == (0, 1)

    def test_wait_finishes_once_the_destination_is_reached(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:
            driver.current_url = CAS_LOGIN_URL
            _, _, submit = driver.add_cas_form()
            checks = []

            def arrived(d) -> bool:
                checks.append(d.current_url)
                return True

            original_click = submit.click

            def click_and_redirect() -> None:
                original_click()
                driver.current_url = COURSE_URL

            submit.click = click_and_redirect

            session.wait_for_login(driver, arrived, timeout=5)

        # Not asked while on the sign-in page; asked once the course page is up.
        assert checks == [COURSE_URL]

    def test_timeout_names_the_page_it_was_stuck_on(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:
            driver.current_url = DUO_URL

            with pytest.raises(AsuLoginError) as error:
                session.wait_for_login(driver, lambda d: True, timeout=0)

        assert DUO_URL in str(error.value)

    def test_closing_the_browser_mid_login_is_reported_plainly(self, factory) -> None:
        session = make_session(factory)
        with session.use() as driver:

            class Gone:
                @property
                def current_url(self):
                    raise WebDriverException("no such window")

            with pytest.raises(AsuLoginError, match="closed"):
                session.wait_for_login(Gone(), lambda d: True, timeout=0)
            assert driver.quit_calls == 0


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (CAS_LOGIN_URL, True),
        (DUO_URL, True),
        ("https://weblogin.asu.edu/serviceauth/oauth2/native/allow?x=catalog.apps.asu.edu", True),
        (COURSE_URL, False),
        ("https://catalog.apps.asu.edu/catalog?code=abc", False),
        ("https://notduosecurity.com/", False),
        ("not a url", False),
    ],
)
def test_on_login_page(url: str, expected: bool) -> None:
    assert on_login_page(url) is expected


def test_host_of_ignores_the_query_string() -> None:
    assert host_of(CAS_LOGIN_URL) == "weblogin.asu.edu"
