from __future__ import annotations

from typing import Optional, Sequence

from GAVEL.app.dtos.roster import ClassSection, RosterRequest, TermInfo
from GAVEL.app.ports.roster_client import RosterClient
from GAVEL.infra.roster.catalog_api import (
    CatalogApiClassResolver,
    ManualTokenProvider,
)
from GAVEL.infra.roster.roster_fetcher import (
    CookieFileRosterFetcher,
    MyASUEndpoints,
    SeleniumRosterFetcher,
)
from GAVEL.infra.roster.shared_auth import SharedAuthProvider


class ASURosterClient(RosterClient):
    """Concrete adapter using SharedAuthProvider for single-login flow."""

    def __init__(
        self,
        shared_auth: SharedAuthProvider,
        class_resolver: CatalogApiClassResolver,
        endpoints: Optional[MyASUEndpoints] = None,
    ) -> None:
        self._auth = shared_auth
        self._resolver = class_resolver
        self._endpoints = endpoints or MyASUEndpoints()

    def list_terms(self) -> Sequence[TermInfo]:
        return self._resolver.list_terms()

    def find_sections(
        self, term: str, subject: str, catalog_number: str,
    ) -> Sequence[ClassSection]:
        return self._resolver.find_sections(term, subject, catalog_number)

    def authenticate(self) -> None:
        self._auth.ensure_authenticated()

    def fetch_roster(self, request: RosterRequest) -> str:
        session = self._auth.get_roster_session()
        params = {
            "term": request.term,
            "class": request.class_number,
            "format": "csv",
        }
        response = session.get(
            self._endpoints.roster_url, params=params, timeout=30,
        )
        SeleniumRosterFetcher._check_response(response)
        return response.text

    def close(self) -> None:
        self._auth.close()


def build_selenium_roster_client(
    token: Optional[str] = None,
) -> ASURosterClient:
    """Build a roster client with shared Selenium auth (one login for both)."""
    shared_auth = SharedAuthProvider()

    if token:
        resolver = CatalogApiClassResolver(
            token_provider=ManualTokenProvider(token),
        )
    else:
        # SharedAuthProvider.obtain_token() is compatible with the
        # token_provider interface that CatalogApiClassResolver expects.
        resolver = CatalogApiClassResolver(token_provider=shared_auth)

    return ASURosterClient(shared_auth=shared_auth, class_resolver=resolver)


def build_cookie_roster_client(
    cookie_file: str,
    token: Optional[str] = None,
) -> CookieASURosterClient:
    """Build a roster client using cookie-file auth (no Selenium)."""
    if token:
        resolver = CatalogApiClassResolver(
            token_provider=ManualTokenProvider(token),
        )
    else:
        resolver = CatalogApiClassResolver()
    fetcher = CookieFileRosterFetcher(cookie_file_path=cookie_file)
    return CookieASURosterClient(class_resolver=resolver, roster_fetcher=fetcher)


class CookieASURosterClient(RosterClient):
    """Adapter for cookie-file-based auth (no shared Selenium session needed)."""

    def __init__(
        self,
        class_resolver: CatalogApiClassResolver,
        roster_fetcher: CookieFileRosterFetcher,
    ) -> None:
        self._resolver = class_resolver
        self._fetcher = roster_fetcher

    def list_terms(self) -> Sequence[TermInfo]:
        return self._resolver.list_terms()

    def find_sections(
        self, term: str, subject: str, catalog_number: str,
    ) -> Sequence[ClassSection]:
        return self._resolver.find_sections(term, subject, catalog_number)

    def authenticate(self) -> None:
        self._fetcher.authenticate()

    def fetch_roster(self, request: RosterRequest) -> str:
        return self._fetcher.fetch_roster(request)

    def close(self) -> None:
        self._fetcher.close()
