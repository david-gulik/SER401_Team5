from argparse import Namespace
from types import SimpleNamespace

import pytest

from GAVEL.cli import main as cli_main
from GAVEL.cli.commands.asu_login import handle_asu_login_forget
from GAVEL.infra.asu_auth import cookie_store


class FakeBrowser:
    def __init__(self, had_saved_login: bool = True) -> None:
        self._had_saved_login = had_saved_login
        self.forget_calls = 0
        self.close_calls = 0

    def forget(self) -> bool:
        self.forget_calls += 1
        return self._had_saved_login

    def close(self) -> None:
        self.close_calls += 1


def make_context(browser):
    return SimpleNamespace(services=SimpleNamespace(asu_browser=browser))


def test_forget_removes_the_saved_login(capsys):
    browser = FakeBrowser(had_saved_login=True)

    result = handle_asu_login_forget(make_context(browser), Namespace())

    assert result == 0
    assert browser.forget_calls == 1
    assert "removed" in capsys.readouterr().out


def test_forget_says_so_when_there_is_nothing_saved(capsys):
    result = handle_asu_login_forget(make_context(FakeBrowser(had_saved_login=False)), Namespace())

    assert result == 0
    assert "No saved ASU login" in capsys.readouterr().out


def test_forget_works_without_a_shared_browser(monkeypatch, tmp_path, capsys):
    saved = tmp_path / "asu_login_cookies.json"
    saved.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(cookie_store, "default_cookie_path", lambda: saved)

    result = handle_asu_login_forget(make_context(None), Namespace())

    assert result == 0
    assert not saved.exists()
    assert "removed" in capsys.readouterr().out


def test_login_browser_is_closed_when_a_command_finishes(monkeypatch):
    browser = FakeBrowser()
    monkeypatch.setattr(cli_main, "_build_app_context", lambda: make_context(browser))

    assert cli_main.main(["asu-login", "forget"]) == 0

    assert browser.close_calls == 1


def test_login_browser_is_closed_when_a_command_raises(monkeypatch):
    browser = FakeBrowser()

    def explode() -> bool:
        raise RuntimeError("boom")

    browser.forget = explode
    monkeypatch.setattr(cli_main, "_build_app_context", lambda: make_context(browser))

    with pytest.raises(RuntimeError, match="boom"):
        cli_main.main(["asu-login", "forget"])

    assert browser.close_calls == 1
