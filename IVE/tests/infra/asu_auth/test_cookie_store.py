"""The saved login is a plain file: what goes in, what comes back, and what is refused."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from GAVEL.infra.asu_auth import cookie_store
from GAVEL.infra.asu_auth.cookie_store import CookieStore, default_cookie_path, restorable

NOW = 1_000_000.0


@pytest.fixture
def store(tmp_path: Path) -> CookieStore:
    return CookieStore(tmp_path / "GAVEL" / "asu_login_cookies.json")


def cookie(name: str, domain: str, **extra) -> dict:
    return {"name": name, "value": f"{name}-value", "domain": domain, "path": "/", **extra}


def test_round_trip_keeps_login_cookies(store: CookieStore) -> None:
    store.save(
        [
            cookie("TGC", "weblogin.asu.edu", httpOnly=True, secure=True),
            cookie("trust", "api-ab654001.duosecurity.com", expires=4_000_000_000),
        ]
    )

    loaded = store.load()

    assert [c["name"] for c in loaded] == ["TGC", "trust"]
    assert loaded[0]["httpOnly"] is True
    assert loaded[1]["expires"] == 4_000_000_000


def test_missing_file_loads_as_no_cookies(store: CookieStore) -> None:
    assert store.load() == []


@pytest.mark.parametrize("content", ["{not json", '{"cookies": []}', ""])
def test_unusable_file_loads_as_no_cookies(store: CookieStore, content: str) -> None:
    store.path.parent.mkdir(parents=True)
    store.path.write_text(content, encoding="utf-8")

    assert store.load() == []


def test_cookies_for_other_sites_are_not_saved(store: CookieStore) -> None:
    store.save(
        [
            cookie("canvas_session", ".canvas.asu.edu"),
            cookie("_gradescope_session", "www.gradescope.com"),
            cookie("tracker", "notasu.edu"),
            cookie("NID", ".google.com"),
        ]
    )

    assert [c["name"] for c in json.loads(store.path.read_text(encoding="utf-8"))] == [
        "canvas_session"
    ]


def test_expired_cookies_are_dropped_and_session_cookies_kept() -> None:
    kept = restorable(
        [
            cookie("expired", "asu.edu", expires=NOW - 1),
            cookie("fresh", "asu.edu", expires=NOW + 60),
            cookie("session", "asu.edu", expires=-1, session=True, size=12),
        ],
        now=NOW,
    )

    assert [c["name"] for c in kept] == ["fresh", "session"]
    # A session cookie goes back without an expiry or Chrome's read-only fields.
    assert kept[1] == {
        "name": "session",
        "value": "session-value",
        "domain": "asu.edu",
        "path": "/",
    }


def test_saving_nothing_worth_keeping_removes_the_file(store: CookieStore) -> None:
    store.save([cookie("TGC", "weblogin.asu.edu")])
    assert store.path.exists()

    store.save([cookie("NID", ".google.com")])

    assert not store.path.exists()


def test_save_leaves_no_temporary_file_behind(store: CookieStore) -> None:
    store.save([cookie("TGC", "weblogin.asu.edu")])

    assert [p.name for p in store.path.parent.iterdir()] == [store.path.name]


def test_clear_reports_whether_there_was_a_saved_login(store: CookieStore) -> None:
    store.save([cookie("TGC", "weblogin.asu.edu")])

    assert store.clear() is True
    assert store.clear() is False
    assert not store.path.exists()


@pytest.mark.parametrize(
    ("platform", "env_var", "expected_parts"),
    [
        ("win32", "LOCALAPPDATA", ("appdata", "GAVEL")),
        ("linux", "XDG_STATE_HOME", ("appdata", "GAVEL")),
        ("darwin", None, ("Library", "Application Support", "GAVEL")),
    ],
)
def test_default_location_is_the_users_app_data_folder(
    monkeypatch, tmp_path, platform, env_var, expected_parts
) -> None:
    monkeypatch.setattr(cookie_store.sys, "platform", platform)
    monkeypatch.setattr(cookie_store.Path, "home", classmethod(lambda cls: tmp_path))
    if env_var:
        monkeypatch.setenv(env_var, str(tmp_path / "appdata"))

    path = default_cookie_path()

    assert path == tmp_path.joinpath(*expected_parts) / "asu_login_cookies.json"


def test_default_location_is_outside_the_project_folder() -> None:
    project_root = Path(__file__).resolve().parents[4]

    assert project_root not in default_cookie_path().parents
