"""
Shared authentication provider for ASU roster services.

Uses the app's shared login browser to get through CAS + Duo MFA once, then
obtains both:
  1. A catalog API JWT (from catalog.apps.asu.edu sessionStorage)
  2. Roster download cookies (from webapp4.asu.edu)

The browser belongs to the app, not to this provider: it stays open after the
roster work is done so other features (and later roster downloads) find it
already signed in.
"""

from __future__ import annotations

import logging
import threading
import time

import requests

from GAVEL.infra.asu_auth.browser_session import AsuBrowserSession, host_of
from GAVEL.services.config_service import RosterConfig

logger = logging.getLogger(__name__)


class SharedAuthProvider:
    """Catalog API token and roster cookies from one login in the shared browser."""

    def __init__(self, roster_cfg: RosterConfig, browser: AsuBrowserSession) -> None:
        self._cfg = roster_cfg
        self._browser = browser

        self._catalog_token: str | None = None
        self._roster_session: requests.Session | None = None
        self._authenticated_at: float | None = None
        self._signed_in_before = False  # this provider has completed a login in the browser
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
        # Try a silent refresh before forcing a full re-login. Only worth it
        # once a login has succeeded here: in a browser that was never signed
        # in, the silent attempt just waits out its timeout before the real
        # sign-in page is shown.
        if self._signed_in_before and self._browser.is_open and self._try_silent_refresh():
            self._restart_keepalive()
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
        """Release the cached roster HTTP session and token.

        The shared browser is left running; whoever owns it closes it when the
        app exits.
        """
        self._keepalive_stop.set()
        if self._roster_session:
            self._roster_session.close()
            self._roster_session = None
        self._authenticated_at = None

    # -- Internals ----------------------------------------------------------

    def _authenticate(self) -> None:
        """Obtain catalog token + roster cookies, logging in only if the browser must."""
        self._keepalive_stop.set()

        with self._browser.use() as driver:
            # Phase 1: catalog API token
            if self._browser.has_credentials:
                print(
                    "[AUTH] Browser ready. Canvas credentials are filled in automatically; "
                    "approve the Duo prompt on your device if one appears "
                    f"(timeout: {self._cfg.mfa_timeout}s)."
                )
            else:
                print(
                    f"[AUTH] Browser ready. If a sign-in page appears, complete CAS login "
                    f"and Duo MFA.\n"
                    f"[AUTH] Tip: set CANVAS_USERNAME and CANVAS_PASSWORD in .env to auto-fill.\n"
                    f"[AUTH] Waiting up to {self._cfg.mfa_timeout}s..."
                )
            self._catalog_token = self._obtain_catalog_token(driver)
            print("[AUTH] Catalog API token acquired.")

            # Phase 2: roster cookies (CAS session already active — no second MFA)
            print("[AUTH] Navigating to MyASU for roster cookies...")
            self._roster_session = self._obtain_roster_session(driver)
            print("[AUTH] Roster session ready.")

        self._authenticated_at = time.time()
        self._signed_in_before = True
        self._restart_keepalive()

    def _try_silent_refresh(self) -> bool:
        """Attempt to refresh credentials using the existing CAS session.

        Uses the passive serviceauth endpoint — if the CAS session in the
        browser is still valid, this returns a new JWT without any user
        interaction.  Roster cookies are then collected from MyASU again,
        which the same CAS session lets through without a prompt.

        Returns True if refresh succeeded, False otherwise.
        """
        import secrets as _secrets
        from urllib.parse import urlencode

        from GAVEL.infra.roster.catalog_api import ServiceAuthConfig
        from GAVEL.infra.roster.pkce import (
            compute_code_challenge,
            generate_code_verifier,
        )

        logger.info("Attempting silent token refresh...")

        try:
            with self._browser.use(show=False) as driver:
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

                    if host_of(current) == catalog_domain:
                        # Give the SPA a moment to exchange the code for a JWT.
                        for _ in range(self._cfg.token_exchange_timeout):
                            token = self._read_session_storage(driver, SS_TOKEN_KEY)
                            if token:
                                # Roster cookies belong to the MyASU site, so
                                # they have to be read while the browser is
                                # there, not from the catalog page.
                                roster_session = self._obtain_roster_session(driver)
                                self._catalog_token = token
                                self._roster_session = roster_session
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

    def _restart_keepalive(self) -> None:
        """Stop any running keepalive and start one for the current roster session."""
        self._keepalive_stop.set()
        self._keepalive_stop = threading.Event()
        self._start_keepalive()

    def _start_keepalive(self) -> None:
        """Ping MyASU periodically to prevent roster session timeout."""
        interval = max(self._cfg.session_ttl // 3, 30)
        stop = self._keepalive_stop

        def _ping() -> None:
            while not stop.wait(timeout=interval):
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

        # 2. Drop any token left in this tab by an earlier login (the browser
        #    is reused), then seed PKCE params into sessionStorage.
        driver.execute_script(f"sessionStorage.removeItem('{SS_TOKEN_KEY}');")

        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier)
        state = _secrets.token_urlsafe(16)

        driver.execute_script(
            f"sessionStorage.setItem('catalog.serviceauth.codeVerifier', '{verifier}');"
        )
        driver.execute_script(f"sessionStorage.setItem('catalog.serviceauth.state', '{state}');")

        # 3. Jump straight to the serviceauth login — goes to CAS
        #    immediately instead of waiting for the SPA to detect no auth.
        #    A browser that is already signed in comes straight back.
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

        # 4. Wait for the browser to land back on the catalog domain, helping
        #    any CAS + Duo login along.  The full MFA timeout applies here.
        #    The host is compared, not the whole URL: the CAS page's address
        #    contains the catalog domain in its query string.
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

            self._browser.assist_login(driver)

            if host_of(current) == catalog_domain:
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
                if host_of(driver.current_url) == domain:
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

            if host_of(current) == myasu_domain:
                time.sleep(3)
                try:
                    final_url = driver.current_url
                except Exception:
                    break

                if host_of(final_url) == myasu_domain:
                    authenticated = True
                    break
            else:
                self._browser.assist_login(driver)

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
