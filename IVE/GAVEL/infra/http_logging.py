"""One terminal line per HTTP call, so a long download shows what it is waiting on."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit, urlunsplit

log = logging.getLogger("GAVEL.http")


def log_http_calls(session: Any) -> None:
    """Log every response ``session`` receives: method, URL, status, time and size.

    Query strings are left out because signed file links carry their access
    token there. Sessions without request hooks (test fakes) are left alone.
    """
    hooks = getattr(session, "hooks", None)
    if not isinstance(hooks, dict):
        return
    hooks.setdefault("response", []).append(_log_response)


def _log_response(response: Any, *args: Any, **kwargs: Any) -> None:
    request = response.request
    size = response.headers.get("Content-Length")
    log.info(
        "%s %s -> %s (%.2f s%s)",
        request.method,
        without_query(request.url),
        response.status_code,
        response.elapsed.total_seconds(),
        f", {_human_size(int(size))}" if size and size.isdigit() else "",
    )


def without_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
