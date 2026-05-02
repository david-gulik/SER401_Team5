"""
Adapters for fetching faculty roster CSVs from ASU's MyASU system.

The only remaining fetcher is CookieFileRosterFetcher, which loads cookies
from a Netscape-format cookie file for headless operation. Selenium-backed
auth now lives in SharedAuthProvider, which supplies a requests.Session
directly to ASURosterClient.
"""

from __future__ import annotations

import http.cookiejar
import logging
from dataclasses import dataclass

import requests

from GAVEL.app.dtos.roster import RosterRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MyASUEndpoints:
    """URL definitions for the MyASU roster system."""

    cas_login: str = "https://weblogin.asu.edu/cas/login"
    myasu_base: str = "https://webapp4.asu.edu/myasu"
    roster_path: str = "/faculty/roster"

    @property
    def roster_url(self) -> str:
        return f"{self.myasu_base}{self.roster_path}"


# ---------------------------------------------------------------------------
# Shared fetch helpers
# ---------------------------------------------------------------------------


def fetch_roster_csv(
    session: requests.Session,
    endpoints: MyASUEndpoints,
    request: RosterRequest,
    http_timeout: int,
) -> str:
    """Download a roster CSV using an already-authenticated session."""
    params = {
        "term": request.term,
        "class": request.class_number,
        "format": "csv",
    }
    response = session.get(
        endpoints.roster_url,
        params=params,
        timeout=http_timeout,
    )
    check_roster_response(response)
    return response.text


def check_roster_response(response: requests.Response) -> None:
    """Raise RuntimeError if the response is not a valid roster CSV."""
    if response.status_code != 200:
        raise RuntimeError(f"Roster fetch failed: HTTP {response.status_code}\nURL: {response.url}")
    if "weblogin.asu.edu" in response.url:
        raise RuntimeError(
            "Session expired or invalid. Re-authentication required.\n"
            f"Redirected to: {response.url}"
        )
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type and "<html" in response.text[:500].lower():
        snippet = response.text[:1000]
        title = ""
        if "<title>" in snippet.lower():
            start = snippet.lower().index("<title>") + 7
            end = (
                snippet.lower().index("</title>", start)
                if "</title>" in snippet.lower()
                else start + 100
            )
            title = snippet[start:end].strip()

        logger.debug("HTML response body (first 1000 chars): %s", snippet)
        raise RuntimeError(
            f"Received HTML instead of CSV.\n"
            f"Page title: {title or '(unknown)'}\n"
            f"URL: {response.url}\n"
            f"This may indicate insufficient permissions (faculty access required)\n"
            f"or an invalid term/class combination."
        )


# ---------------------------------------------------------------------------
# Cookie-file-based roster fetcher
# ---------------------------------------------------------------------------


class CookieFileRosterFetcher:
    """
    Loads cookies from a Netscape-format cookie file and uses them
    to download roster CSVs without Selenium.
    """

    def __init__(
        self,
        cookie_file_path: str,
        endpoints: MyASUEndpoints | None = None,
        http_timeout: int = 30,
    ):
        self._cookie_path = cookie_file_path
        self._endpoints = endpoints or MyASUEndpoints()
        self._http_timeout = http_timeout
        self._session: requests.Session | None = None

    def authenticate(self) -> None:
        jar = http.cookiejar.MozillaCookieJar(self._cookie_path)
        jar.load(ignore_discard=True, ignore_expires=True)

        self._session = requests.Session()
        self._session.cookies = jar
        self._session.headers.update(
            {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")}
        )
        logger.info("Loaded %d cookies from %s", len(jar), self._cookie_path)

    def fetch_roster(self, request: RosterRequest) -> str:
        if self._session is None:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return fetch_roster_csv(
            self._session,
            self._endpoints,
            request,
            self._http_timeout,
        )

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None
