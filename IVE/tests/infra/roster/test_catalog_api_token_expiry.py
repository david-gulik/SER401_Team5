"""What the catalog client does when the API answers 401 (token expired)."""

from __future__ import annotations

import pytest

from GAVEL.infra.roster.catalog_api import CatalogApiClassResolver, ManualTokenProvider


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def json(self) -> dict:
        return self._payload


class FakeHttp:
    """Accepts only the token named ``good``; records the tokens it was shown."""

    def __init__(self, good: str | None) -> None:
        self.headers: dict[str, str] = {}
        self._good = good
        self.seen: list[str] = []

    def get(self, url: str, timeout: int) -> FakeResponse:
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        self.seen.append(token)
        if token == self._good:
            return FakeResponse(200, {"fullList": [{"value": "2261", "label": "Spring 2026"}]})
        return FakeResponse(401)


class CachingProvider:
    """Like the browser login: keeps handing out its token until told to sign in again."""

    def __init__(self) -> None:
        self._token = "expired"
        self.invalidations = 0

    def obtain_token(self) -> str:
        return self._token

    def invalidate(self) -> None:
        self.invalidations += 1
        self._token = "fresh"


def make_resolver(provider, good_token: str | None) -> tuple[CatalogApiClassResolver, FakeHttp]:
    resolver = CatalogApiClassResolver(token_provider=provider)
    http = FakeHttp(good_token)
    resolver._session = http
    return resolver, http


def test_expired_token_makes_the_provider_sign_in_again_then_retries() -> None:
    provider = CachingProvider()
    resolver, http = make_resolver(provider, good_token="fresh")

    terms = resolver.list_terms()

    assert [t.code for t in terms] == ["2261"]
    assert provider.invalidations == 1
    assert http.seen == ["expired", "fresh"]


def test_token_still_rejected_after_a_new_login_is_a_clear_error() -> None:
    provider = CachingProvider()
    resolver, http = make_resolver(provider, good_token=None)

    with pytest.raises(RuntimeError, match="rejected the login token"):
        resolver.list_terms()

    assert len(http.seen) == 2


def test_expired_token_from_the_env_file_says_how_to_fix_it() -> None:
    resolver, _ = make_resolver(ManualTokenProvider("pasted-long-ago"), good_token=None)

    with pytest.raises(RuntimeError, match="ROSTER_TOKEN"):
        resolver.list_terms()
