"""Adapter: resolves class sections via ASU's catalog JSON API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import requests

from GAVEL.app.dtos.roster import ClassSection, TermInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OAuth configuration (extracted from catalog SPA bundle.js)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServiceAuthConfig:
    """OAuth endpoints and credentials for ASU's serviceauth system."""

    token_url: str = (
        "https://weblogin.asu.edu/serviceauth/oauth2/native/token"
    )
    passive_allow_url: str = (
        "https://weblogin.asu.edu/serviceauth/oauth2/passive/native/allow"
    )
    active_allow_url: str = (
        "https://weblogin.asu.edu/serviceauth/oauth2/native/allow"
    )
    client_id: str = "catalog-class-search-app"
    client_secret: str = "serviceauth-public-agent"
    redirect_uri: str = "https://catalog.apps.asu.edu/catalog"
    scopes: tuple[str, ...] = (
        "https://api.myasuplat-dpl.asu.edu/scopes/principal/read:self",
        "https://api.myasuplat-dpl.asu.edu/scopes/person/read:self",
        "https://api.myasuplat-dpl.asu.edu/scopes/acad-plan/read:self",
    )


# ---------------------------------------------------------------------------
# Catalog API configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CatalogApiConfig:
    """Endpoint URLs for the catalog search API."""

    base_url: str = (
        "https://eadvs-cscc-catalog-api.apps.asu.edu"
        "/catalog-microservices/api/v1/search"
    )

    @property
    def classes_url(self) -> str:
        return f"{self.base_url}/classes"

    @property
    def terms_url(self) -> str:
        return f"{self.base_url}/terms"

    @property
    def subjects_url(self) -> str:
        return f"{self.base_url}/subjects"


# ---------------------------------------------------------------------------
# Token acquisition
# ---------------------------------------------------------------------------

class ServiceAuthTokenProvider:
    """
    Obtains Bearer tokens via ASU's serviceauth PKCE OAuth flow.

    Opens a Selenium browser for CAS + Duo MFA, then intercepts the JWT
    from the catalog SPA's sessionStorage.
    """

    def __init__(
        self,
        config: Optional[ServiceAuthConfig] = None,
        mfa_timeout_seconds: int = 120,
    ):
        self._config = config or ServiceAuthConfig()
        self._mfa_timeout = mfa_timeout_seconds

    def obtain_token(self) -> str:
        import time
        import secrets as _secrets
        from GAVEL.infra.roster.pkce import generate_code_verifier, compute_code_challenge

        SS_TOKEN_KEY = "catalog.jwt.token"
        catalog_domain = "catalog.apps.asu.edu"

        driver = self._create_driver()
        try:
            driver.get(self._config.redirect_uri)

            print(
                f"[AUTH] Browser opened. Complete CAS login and Duo MFA.\n"
                f"[AUTH] Waiting up to {self._mfa_timeout}s..."
            )

            deadline = time.time() + self._mfa_timeout
            last_printed_url = ""
            token = None

            while time.time() < deadline:
                try:
                    current = driver.current_url
                except Exception:
                    break

                if current != last_printed_url:
                    display = current[:120] + ("..." if len(current) > 120 else "")
                    print(f"[AUTH] Current URL: {display}")
                    last_printed_url = current

                if catalog_domain in current:
                    token = self._read_session_storage(driver, SS_TOKEN_KEY)
                    if token:
                        print("[AUTH] Token found in sessionStorage.")
                        break

                    for _ in range(5):
                        time.sleep(1)
                        token = self._read_session_storage(driver, SS_TOKEN_KEY)
                        if token:
                            print("[AUTH] Token found in sessionStorage.")
                            break

                    if token:
                        break

                    print("[AUTH] No token yet. Triggering OAuth flow...")
                    token = self._trigger_oauth_flow(driver, deadline)
                    break

                time.sleep(1)

            if not token:
                try:
                    last_url = driver.current_url
                except Exception:
                    last_url = last_printed_url
                raise RuntimeError(
                    f"Could not obtain token.\n"
                    f"Last URL: {last_url}\n"
                    f"Make sure you completed CAS login and Duo MFA."
                )

            return token
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def _trigger_oauth_flow(self, driver, deadline) -> Optional[str]:
        import time
        import secrets as _secrets
        from urllib.parse import urlencode as _urlencode
        from GAVEL.infra.roster.pkce import generate_code_verifier, compute_code_challenge

        SS_TOKEN_KEY = "catalog.jwt.token"

        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier)
        state = _secrets.token_urlsafe(16)

        driver.execute_script(
            f"sessionStorage.setItem('catalog.serviceauth.codeVerifier', "
            f"'{verifier}');"
        )
        driver.execute_script(
            f"sessionStorage.setItem('catalog.serviceauth.state', "
            f"'{state}');"
        )

        allow_params = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "scope": " ".join(self._config.scopes),
        }
        allow_url = (
            f"{self._config.active_allow_url}?{_urlencode(allow_params)}"
        )

        print("[AUTH] Navigating to serviceauth allow endpoint...")
        driver.get(allow_url)

        last_printed = ""
        while time.time() < deadline:
            try:
                current = driver.current_url
            except Exception:
                break

            if current != last_printed:
                display = current[:120] + ("..." if len(current) > 120 else "")
                print(f"[AUTH] Current URL: {display}")
                last_printed = current

            token = self._read_session_storage(driver, SS_TOKEN_KEY)
            if token:
                print("[AUTH] Token acquired after OAuth redirect.")
                return token

            time.sleep(1)

        return None

    @staticmethod
    def _read_session_storage(driver, key: str) -> Optional[str]:
        try:
            value = driver.execute_script(
                f"return sessionStorage.getItem('{key}');"
            )
            if value and isinstance(value, str) and len(value) > 10:
                return value
        except Exception:
            pass
        return None

    @staticmethod
    def _create_driver():
        from selenium import webdriver
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option(
            "excludeSwitches", ["enable-automation"]
        )
        return webdriver.Chrome(options=options)


class ManualTokenProvider:
    """Token provider that accepts a pre-existing Bearer token."""

    def __init__(self, token: str):
        self._token = token

    def obtain_token(self) -> str:
        return self._token


# ---------------------------------------------------------------------------
# Catalog API client (ClassResolver)
# ---------------------------------------------------------------------------

class CatalogApiClassResolver:
    """
    Resolves class sections via ASU's catalog JSON API.

    Handles token acquisition automatically. On 401, re-authenticates
    transparently.
    """

    def __init__(
        self,
        api_config: Optional[CatalogApiConfig] = None,
        token_provider: Optional[ServiceAuthTokenProvider] = None,
        http_timeout: int = 30,
    ):
        self._api = api_config or CatalogApiConfig()
        self._token_provider = token_provider or ServiceAuthTokenProvider()
        self._http_timeout = http_timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self._token: Optional[str] = None

    def list_terms(self) -> list[TermInfo]:
        data = self._authed_get(self._api.terms_url)
        logger.debug("Terms raw response keys: %s", list(data.keys()) if isinstance(data, dict) else type(data))

        current_terms = []
        if isinstance(data, dict):
            current_terms = data.get("currentTerm", [])
            full_list = data.get("fullList", [])
        elif isinstance(data, list):
            full_list = data
        else:
            full_list = []

        current_codes = {str(t.get("value", "")) for t in current_terms}

        terms = []
        for item in full_list:
            code = str(item.get("value", item.get("strm", "")))
            terms.append(TermInfo(
                code=code,
                name=str(item.get("label", item.get("descr", ""))),
                default=code in current_codes,
            ))
        return terms

    def find_sections(
        self,
        term: str,
        subject: str,
        catalog_number: str,
    ) -> list[ClassSection]:
        params = {
            "refine": "Y",
            "subject": subject.upper(),
            "catalogNbr": catalog_number,
            "term": term,
            "searchType": "all",
        }
        url = f"{self._api.classes_url}?&{urlencode(params)}"
        data = self._authed_get(url)
        return self._parse_classes(data)

    # -- Internals ----------------------------------------------------------

    def _ensure_token(self) -> None:
        if self._token is None:
            self._token = self._token_provider.obtain_token()
            self._session.headers["Authorization"] = f"Bearer {self._token}"

    def _authed_get(self, url: str) -> dict:
        self._ensure_token()

        logger.debug("GET %s", url)
        response = self._session.get(url, timeout=self._http_timeout)
        logger.debug("Response: HTTP %d, %d bytes", response.status_code, len(response.text))

        if response.status_code == 401:
            logger.info("Got 401, refreshing token and retrying.")
            self._token = None
            self._ensure_token()
            response = self._session.get(url, timeout=self._http_timeout)

        if response.status_code != 200:
            raise RuntimeError(
                f"Catalog API error: HTTP {response.status_code} "
                f"for {url} - {response.text[:300]}"
            )

        return response.json()

    @staticmethod
    def _parse_classes(data: dict) -> list[ClassSection]:
        classes_raw = data.get("classes", [])
        sections = []
        for item in classes_raw:
            clas = item.get("CLAS", item)
            sections.append(ClassSection(
                class_number=str(clas.get("CLASSNBR", "")),
                subject=str(clas.get("SUBJECT", "")),
                catalog_number=str(clas.get("CATALOGNBR", "")),
                title=str(clas.get("COURSETITLELONG", clas.get("DESCR", ""))),
                instructor=str(clas.get("INSTRUCTORSLIST", "")),
                days_times=str(clas.get("DAYSTIMES", "")),
                session=str(clas.get("SESSIONCODE", "")),
                campus=str(clas.get("CAMPUS", "")),
                seats_open=int(clas.get("ENRLCAP", 0)) - int(clas.get("ENRLTOT", 0)),
                component=str(clas.get("COMPONENTPRIMARY", "")),
            ))
        return sections
