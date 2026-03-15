"""
Shared authentication provider for ASU services.

Opens a single Selenium browser to authenticate once via CAS + Duo MFA,
then obtains both:
  1. A catalog API JWT (from catalog.apps.asu.edu sessionStorage)
  2. Roster download cookies (from webapp4.asu.edu)

Cached credentials are reused until the TTL expires (default 10 min).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS = 600  # 10 minutes


class SharedAuthProvider:
    """Single Selenium session for both catalog API token and roster cookies."""

    def __init__(
        self,
        mfa_timeout_seconds: int = 120,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        self._mfa_timeout = mfa_timeout_seconds
        self._ttl = ttl_seconds

        self._catalog_token: Optional[str] = None
        self._roster_session: Optional[requests.Session] = None
        self._authenticated_at: Optional[float] = None

    # -- Public API ---------------------------------------------------------

    @property
    def is_valid(self) -> bool:
        if self._authenticated_at is None:
            return False
        return (time.time() - self._authenticated_at) < self._ttl

    def ensure_authenticated(self) -> None:
        """Authenticate if cached credentials are missing or expired."""
        if not self.is_valid:
            self._authenticate()

    def obtain_token(self) -> str:
        """Return a catalog API JWT, authenticating if needed.

        Compatible with CatalogApiClassResolver's token_provider interface.
        """
        self.ensure_authenticated()
        return self._catalog_token

    def get_roster_session(self) -> requests.Session:
        """Return a requests.Session with MyASU cookies, authenticating if needed."""
        self.ensure_authenticated()
        return self._roster_session

    def invalidate(self) -> None:
        """Force re-authentication on next call."""
        self._authenticated_at = None

    def close(self) -> None:
        """Release the cached roster HTTP session."""
        if self._roster_session:
            self._roster_session.close()
            self._roster_session = None
        self._authenticated_at = None

    # -- Internals ----------------------------------------------------------

    def _authenticate(self) -> None:
        """Open one browser, obtain catalog token + roster cookies."""
        driver = self._create_driver()
        try:
            # Phase 1: catalog API token
            print(
                f"[AUTH] Browser opened. Complete CAS login and Duo MFA.\n"
                f"[AUTH] Waiting up to {self._mfa_timeout}s..."
            )
            self._catalog_token = self._obtain_catalog_token(driver)
            print("[AUTH] Catalog API token acquired.")

            # Phase 2: roster cookies (CAS session already active — no second MFA)
            print("[AUTH] Navigating to MyASU for roster cookies...")
            self._roster_session = self._obtain_roster_session(driver)
            print("[AUTH] Roster session ready.")

            self._authenticated_at = time.time()
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    # -- Phase 1: catalog token ---------------------------------------------

    def _obtain_catalog_token(self, driver) -> str:
        import secrets as _secrets
        from urllib.parse import urlencode

        from GAVEL.infra.roster.catalog_api import ServiceAuthConfig
        from GAVEL.infra.roster.pkce import (
            compute_code_challenge,
            generate_code_verifier,
        )

        SS_TOKEN_KEY = "catalog.jwt.token"
        catalog_domain = "catalog.apps.asu.edu"
        config = ServiceAuthConfig()

        # 1. Load a lightweight page on the catalog domain so we can
        #    write to sessionStorage without the SPA redirecting us away.
        driver.get("https://catalog.apps.asu.edu/favicon.ico")
        self._wait_for_domain(driver, catalog_domain, timeout=30)

        # 2. Seed PKCE params into sessionStorage.
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier)
        state = _secrets.token_urlsafe(16)

        driver.execute_script(
            f"sessionStorage.setItem('catalog.serviceauth.codeVerifier', '{verifier}');"
        )
        driver.execute_script(
            f"sessionStorage.setItem('catalog.serviceauth.state', '{state}');"
        )

        # 3. Jump straight to the serviceauth login — goes to CAS
        #    immediately instead of waiting for the SPA to detect no auth.
        allow_params = {
            "response_type": "code",
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "scope": " ".join(config.scopes),
        }
        allow_url = f"{config.active_allow_url}?{urlencode(allow_params)}"

        print("[AUTH] Redirecting to CAS login...")
        driver.get(allow_url)

        # 4. Wait for user to complete CAS + Duo MFA and land back on
        #    the catalog domain.  The full MFA timeout applies here.
        deadline = time.time() + self._mfa_timeout
        last_printed = ""
        token = None

        while time.time() < deadline:
            try:
                current = driver.current_url
            except Exception:
                break

            if current != last_printed:
                display = current[:120] + ("..." if len(current) > 120 else "")
                print(f"[AUTH] Current URL: {display}")
                last_printed = current

            if catalog_domain in current:
                # SPA received ?code= and should exchange it for a JWT.
                # Give it up to 30 s — the exchange can be slow on first load.
                for _ in range(30):
                    token = self._read_session_storage(driver, SS_TOKEN_KEY)
                    if token:
                        break
                    time.sleep(1)
                break

            time.sleep(1)

        if not token:
            try:
                last_url = driver.current_url
            except Exception:
                last_url = last_printed
            raise RuntimeError(
                f"Could not obtain catalog token.\n"
                f"Last URL: {last_url}\n"
                f"Make sure you completed CAS login and Duo MFA."
            )

        return token

    @staticmethod
    def _wait_for_domain(driver, domain: str, timeout: int = 30) -> None:
        """Block until the browser is on the given domain (or timeout)."""
        import time as _time

        deadline = _time.time() + timeout
        while _time.time() < deadline:
            try:
                if domain in driver.current_url:
                    return
            except Exception:
                return
            _time.sleep(0.5)

    # -- Phase 2: roster cookies --------------------------------------------

    def _obtain_roster_session(self, driver) -> requests.Session:
        myasu_base = "https://webapp4.asu.edu/myasu"
        myasu_domain = "webapp4.asu.edu"

        driver.get(f"{myasu_base}/")

        deadline = time.time() + self._mfa_timeout
        last_printed_url = ""
        authenticated = False

        while time.time() < deadline:
            try:
                current = driver.current_url
            except Exception:
                break

            if current != last_printed_url:
                display = current[:120] + ("..." if len(current) > 120 else "")
                print(f"[AUTH] Current URL: {display}")
                last_printed_url = current

            if myasu_domain in current and "cas/login" not in current:
                time.sleep(3)
                try:
                    final_url = driver.current_url
                except Exception:
                    break

                if myasu_domain in final_url and "cas/login" not in final_url:
                    authenticated = True
                    break

            time.sleep(1)

        if not authenticated:
            try:
                last_url = driver.current_url
            except Exception:
                last_url = last_printed_url
            raise RuntimeError(
                f"MyASU authentication failed.\nLast URL: {last_url}"
            )

        return self._transfer_cookies(driver)

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _create_driver():
        from selenium import webdriver

        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option(
            "excludeSwitches", ["enable-automation"]
        )
        return webdriver.Chrome(options=options)

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
    def _transfer_cookies(driver) -> requests.Session:
        session = requests.Session()
        for cookie in driver.get_cookies():
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )
        session.headers.update({
            "User-Agent": driver.execute_script("return navigator.userAgent")
        })
        return session
