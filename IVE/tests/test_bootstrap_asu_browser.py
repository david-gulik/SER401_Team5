"""How the app assembles its shared login browser from configuration."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from GAVEL.bootstrap import build_asu_browser, build_roster_client
from GAVEL.infra.asu_auth import cookie_store
from GAVEL.services.config_service import ConfigService


@pytest.fixture
def saved_login(monkeypatch, tmp_path):
    path = tmp_path / "GAVEL" / "asu_login_cookies.json"
    monkeypatch.setattr(cookie_store, "default_cookie_path", lambda: path)
    return path


def config(**env: str):
    return ConfigService(env=env).get()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        ("", True),
        ("true", True),
        ("TRUE", True),
        ("false", False),
        (" False ", False),
        ("0", False),
        ("off", False),
    ],
)
def test_remember_setting_defaults_to_on(value, expected) -> None:
    env = {} if value is None else {"ASU_LOGIN_REMEMBER": value}

    assert config(**env).asu_login.remember is expected


def test_login_is_remembered_by_default(saved_login) -> None:
    browser = build_asu_browser(config(), Mock())

    assert browser.remembers_login is True
    assert browser.is_open is False  # nothing opens until a download needs it


def test_turning_the_setting_off_also_deletes_a_saved_login(saved_login) -> None:
    saved_login.parent.mkdir(parents=True)
    saved_login.write_text("[]", encoding="utf-8")

    browser = build_asu_browser(config(ASU_LOGIN_REMEMBER="false"), Mock())

    assert browser.remembers_login is False
    assert not saved_login.exists()


def test_login_wait_uses_the_configured_mfa_timeout(saved_login) -> None:
    browser = build_asu_browser(config(ROSTER_MFA_TIMEOUT="45"), Mock())

    assert browser.mfa_timeout == 45


def test_roster_client_signs_in_through_the_shared_browser(saved_login) -> None:
    cfg = config(ROSTER_AUTH_METHOD="selenium")
    browser = build_asu_browser(cfg, Mock())

    client = build_roster_client(cfg, Mock(), browser)

    assert client._auth._browser is browser
    client.close()
    assert browser.is_open is False
