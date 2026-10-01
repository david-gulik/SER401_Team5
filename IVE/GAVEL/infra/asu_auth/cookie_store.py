"""Keeps the login browser's cookies on disk between runs of the app.

The file is the same thing a logged-in browser holds: whoever can read it can
act as the user until the cookies expire. It therefore lives in the user's own
application-data folder, never in the project folder, and is written with
owner-only permissions where the platform supports them.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Only the sites that decide whether a login is needed are worth keeping:
# ASU single sign-on (which also covers Canvas and MyASU) and Duo.
SAVED_DOMAIN_SUFFIXES: tuple[str, ...] = ("asu.edu", "duosecurity.com")

# The fields Chrome accepts back when cookies are restored.
_COOKIE_FIELDS: tuple[str, ...] = (
    "name",
    "value",
    "domain",
    "path",
    "secure",
    "httpOnly",
    "sameSite",
    "expires",
    "priority",
    "sourceScheme",
    "sourcePort",
    "partitionKey",
)

_FILE_NAME = "asu_login_cookies.json"


def default_cookie_path() -> Path:
    """Per-user location outside the project folder and outside synced documents."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "GAVEL" / _FILE_NAME


def restorable(cookies: list[dict], now: float | None = None) -> list[dict]:
    """Reduce browser cookies to the ones worth restoring into a new browser.

    Drops cookies for unrelated sites and cookies that have already expired,
    and strips each one down to the fields Chrome accepts back. A cookie with
    no expiry (a session cookie) is kept; the site decides whether it is still
    good.
    """
    now = time.time() if now is None else now
    kept: list[dict] = []
    for cookie in cookies:
        if not isinstance(cookie, dict) or not cookie.get("name") or "value" not in cookie:
            continue
        domain = str(cookie.get("domain", "")).lstrip(".").lower()
        if not any(domain == s or domain.endswith(f".{s}") for s in SAVED_DOMAIN_SUFFIXES):
            continue
        expires = cookie.get("expires")
        has_expiry = isinstance(expires, (int, float)) and expires > 0
        if has_expiry and expires <= now:
            continue
        slim = {k: cookie[k] for k in _COOKIE_FIELDS if k in cookie and k != "expires"}
        if has_expiry:
            slim["expires"] = expires
        kept.append(slim)
    return kept


class CookieStore:
    """Reads and writes one JSON file of login cookies."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_cookie_path()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[dict]:
        """Saved cookies that can still be restored; empty when there is nothing usable.

        A missing, unreadable, or malformed file is treated the same as no
        file: the caller simply logs in again.
        """
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable saved login at %s: %s", self._path, exc)
            return []
        if not isinstance(data, list):
            logger.warning("Ignoring saved login at %s: unexpected format.", self._path)
            return []
        return restorable(data)

    def save(self, cookies: list[dict]) -> None:
        """Replace the file with the given cookies; remove it when none are worth keeping."""
        kept = restorable(cookies)
        if not kept:
            self.clear()
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write beside the target and swap, so a crash never leaves half a file.
        temp = self._path.with_name(self._path.name + ".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(kept, handle)
        os.replace(temp, self._path)

    def clear(self) -> bool:
        """Delete the saved login. Returns True when there was one to delete."""
        try:
            self._path.unlink()
        except FileNotFoundError:
            return False
        return True
