"""
Shared authentication provider for ASU services.

Opens a single Selenium browser to authenticate once via CAS + Duo MFA,
then obtains both:
  1. A catalog API JWT (from catalog.apps.asu.edu sessionStorage)
  2. Roster download cookies (from webapp4.asu.edu)

The browser is kept alive after initial auth so that credentials can be
silently refreshed without requiring the user to log in again.
"""

from __future__ import annotations

import logging
import threading
import time

import requests

from GAVEL.services.config_service import RosterConfig

logger = logging.getLogger(__name__)


class SharedAuthProvider:
    """Single Selenium session for both catalog API token and roster cookies.

    The browser persists after initial login so the CAS session can be reused
    for silent token refreshes and roster cookie renewal.
    """

    def __init__(self, roster_cfg: RosterConfig) -> None:
        self._cfg = roster_cfg

        self._catalog_token: str | None = None
        self._roster_session: requests.Session | None = None
        self._authenticated_at: float | None = None
        self._driver = None
        self._keepalive_stop = threading.Event()

    # -- Public API ---------------------------------------------------------

    @property
    def is_valid(self) -> bool:
        if self._authenticated_at is None:
            return False
        return (time.time() - self._authenticated_at) < self._cfg.session_ttl

    def ensure_authenticated(self) -> None:
        """Authenticate if cached credentials are missing or expired."""
        if self.is_valid:
            return
        # Try a silent refresh before forcing a full re-login.
        if self._driver is not None and self._try_silent_refresh():
            return
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
        """Release the browser and cached roster HTTP session."""
        self._keepalive_stop.set()
        if self._roster_session:
            self._roster_session.close()
            self._roster_session = None
        self._quit_driver()
        self._authenticated_at = None

    # -- Internals ----------------------------------------------------------

    def _authenticate(self) -> None:
        """Open one browser, obtain catalog token + roster cookies."""
        # Clean up any previous driver before starting fresh.
        self._keepalive_stop.set()
        self._quit_driver()

        self._driver = self._create_driver()
        try:
            # Phase 1: catalog API token
            print(
                f"[AUTH] Browser opened. Complete CAS login and Duo MFA.\n"
                f"[AUTH] Waiting up to {self._cfg.mfa_timeout}s..."
            )
            self._catalog_token = self._obtain_catalog_token(self._driver)
            print("[AUTH] Catalog API token acquired.")

            # Phase 2: roster cookies (CAS session already active — no second MFA)
            print("[AUTH] Navigating to MyASU for roster cookies...")
            self._roster_session = self._obtain_roster_session(self._driver)
            print("[AUTH] Roster session ready.")

            self._authenticated_at = time.time()

            # Minimize the browser window now that MFA is done.
            try:
                self._driver.minimize_window()
            except Exception:
                pass

            # Start background keepalive for the roster session.
            self._keepalive_stop = threading.Event()
            self._start_keepalive()

        except Exception:
            # Only quit the driver on failure; on success we keep it alive.
            self._quit_driver()
            raise

    def _try_silent_refresh(self) -> bool:
        """Attempt to refresh credentials using the existing CAS session.

        Uses the passive serviceauth endpoint — if the CAS session in the
        browser is still valid, this returns a new JWT without any user
        interaction.  Also re-transfers roster cookies from the browser.

        Returns True if refresh succeeded, False otherwise.
        """
        import secrets as _secrets
        from urllib.parse import urlencode

        from GAVEL.infra.roster.catalog_api import ServiceAuthConfig
        from GAVEL.infra.roster.pkce import (
            compute_code_challenge,
            generate_code_verifier,
        )

        driver = self._driver
        if driver is None:
            return False

        logger.info("Attempting silent token refresh...")

        try:
            config = ServiceAuthConfig()
            SS_TOKEN_KEY = "catalog.jwt.token"
            catalog_domain = "catalog.apps.asu.edu"

            # Navigate to a lightweight page on the catalog domain to access
            # sessionStorage.
            driver.get("https://catalog.apps.asu.edu/favicon.ico")
            self._wait_for_domain(
                driver,
                catalog_domain,
                timeout=self._cfg.page_load_timeout,
            )

            # Clear the old token so we know if we get a fresh one.
            driver.execute_script(f"sessionStorage.removeItem('{SS_TOKEN_KEY}');")

            # Seed fresh PKCE parameters.
            verifier = generate_code_verifier()
            challenge = compute_code_challenge(verifier)
            state = _secrets.token_urlsafe(16)

            driver.execute_script(
                f"sessionStorage.setItem('catalog.serviceauth.codeVerifier', '{verifier}');"
            )
            driver.execute_script(
                f"sessionStorage.setItem('catalog.serviceauth.state', '{state}');"
            )

            # Use the *passive* allow URL — this will silently redirect back
            # if the CAS session is still valid, or fail without prompting.
            allow_params = {
                "response_type": "code",
                "client_id": config.client_id,
                "redirect_uri": config.redirect_uri,
                "state": state,
                "code_challenge_method": "S256",
                "code_challenge": challenge,
                "scope": " ".join(config.scopes),
            }
            passive_url = f"{config.passive_allow_url}?{urlencode(allow_params)}"

            driver.get(passive_url)

            # Wait for the redirect back to the catalog domain with a token.
            deadline = time.time() + self._cfg.page_load_timeout
            while time.time() < deadline:
                try:
                    current = driver.current_url
                except Exception:
                    return False

                if catalog_domain in current:
                    # Give the SPA a moment to exchange the code for a JWT.
                    for _ in range(self._cfg.token_exchange_timeout):
                        token = self._read_session_storage(driver, SS_TOKEN_KEY)
                        if token:
                            self._catalog_token = token
                            # Re-transfer roster cookies from the browser
                            # in case they were rotated.
                            self._roster_session = self._transfer_cookies(driver)
                            self._authenticated_at = time.time()
                            logger.info("Silent token refresh succeeded.")
                            print("[AUTH] Session refreshed silently.")
                            return True
                        time.sleep(1)
                    # Timed out waiting for the token exchange.
                    return False

                time.sleep(0.5)

        except Exception as exc:
            logger.debug("Silent refresh failed: %s", exc)

        return False

    # -- Keepalive ----------------------------------------------------------

    def _start_keepalive(self) -> None:
        """Ping MyASU periodically to prevent roster session timeout."""
        interval = max(self._cfg.session_ttl // 3, 30)

        def _ping() -> None:
            while not self._keepalive_stop.wait(timeout=interval):
                try:
                    session = self._roster_session
                    if session is None:
                        return

                    resp = session.get(
                        "https://webapp4.asu.edu/myasu/",
                        timeout=10,
                        allow_redirects=False,
                    )
                    location = resp.headers.get("Location", "")
                    if resp.status_code in (301, 302) and "cas/login" in location:
                        logger.warning(
                            "Roster keepalive: redirected to CAS login — session expired."
                        )
                        return
                    logger.debug(
                        "Roster keepalive: HTTP %d",
                        resp.status_code,
                    )
                except Exception as exc:
                    logger.debug("Roster keepalive error: %s", exc)

        t = threading.Thread(target=_ping, daemon=True, name="roster-keepalive")
        t.start()

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
        self._wait_for_domain(
            driver,
            catalog_domain,
            timeout=self._cfg.page_load_timeout,
        )

        # 2. Seed PKCE params into sessionStorage.
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier)
        state = _secrets.token_urlsafe(16)

        driver.execute_script(
            f"sessionStorage.setItem('catalog.serviceauth.codeVerifier', '{verifier}');"
        )
        driver.execute_script(f"sessionStorage.setItem('catalog.serviceauth.state', '{state}');")

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
        deadline = time.time() + self._cfg.mfa_timeout
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
                for _ in range(self._cfg.token_exchange_timeout):
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

        deadline = time.time() + self._cfg.page_load_timeout
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
            raise RuntimeError(f"MyASU authentication failed.\nLast URL: {last_url}")

        return self._transfer_cookies(driver)

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _create_driver():
        from selenium import webdriver

        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        return webdriver.Chrome(options=options)

    def _quit_driver(self) -> None:
        """Safely quit the stored Selenium driver."""
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    @staticmethod
    def _read_session_storage(driver, key: str) -> str | None:
        try:
            value = driver.execute_script(f"return sessionStorage.getItem('{key}');")
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
        session.headers.update({"User-Agent": driver.execute_script("return navigator.userAgent")})
        return session
