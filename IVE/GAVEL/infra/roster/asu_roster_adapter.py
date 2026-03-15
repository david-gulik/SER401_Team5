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
    SeleniumRosterFetcher,
)


class ASURosterClient(RosterClient):
    """Concrete adapter composing a class resolver and a roster fetcher."""

    def __init__(
        self,
        class_resolver: CatalogApiClassResolver,
        roster_fetcher: SeleniumRosterFetcher | CookieFileRosterFetcher,
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


def build_selenium_roster_client(
    token: Optional[str] = None,
) -> ASURosterClient:
    """Build a roster client using Selenium for both catalog auth and roster download."""
    if token:
        resolver = CatalogApiClassResolver(
            token_provider=ManualTokenProvider(token),
        )
    else:
        resolver = CatalogApiClassResolver()
    fetcher = SeleniumRosterFetcher()
    return ASURosterClient(class_resolver=resolver, roster_fetcher=fetcher)


def build_cookie_roster_client(
    cookie_file: str,
    token: Optional[str] = None,
) -> ASURosterClient:
    """Build a roster client using cookie-file auth for roster download."""
    if token:
        resolver = CatalogApiClassResolver(
            token_provider=ManualTokenProvider(token),
        )
    else:
        resolver = CatalogApiClassResolver()
    fetcher = CookieFileRosterFetcher(cookie_file_path=cookie_file)
    return ASURosterClient(class_resolver=resolver, roster_fetcher=fetcher)
