"""
Manual integration test for silent session refresh.

Requires a real ASU account with CAS + Duo MFA — cannot run in CI.

    python -m pytest tests/manual/ -m manual -s

The ``-s`` flag is required so you can see the browser and complete MFA.

Environment variables (or .env):
    ROSTER_AUTH_METHOD=selenium
"""

from __future__ import annotations

import dataclasses
import time

import pytest

from GAVEL.infra.roster.asu_roster_adapter import build_selenium_roster_client
from GAVEL.services.config_service import ConfigService

# Short TTL so we don't have to wait 10 minutes to test refresh.
_TEST_TTL_SECONDS = 30

pytestmark = pytest.mark.manual


@pytest.fixture()
def roster_client():
    cfg = ConfigService().get()

    if (cfg.roster.auth_method or "").lower() != "selenium":
        pytest.skip("ROSTER_AUTH_METHOD != selenium; skipping live auth test")

    roster_cfg = dataclasses.replace(cfg.roster, session_ttl=_TEST_TTL_SECONDS)

    client = build_selenium_roster_client(roster_cfg=roster_cfg)
    yield client
    client.close()


def test_initial_auth_returns_terms(roster_client):
    """First call triggers MFA login and returns terms."""
    terms = roster_client.list_terms()
    assert len(terms) > 0, "Expected at least one academic term"
    print(f"\n[OK] Got {len(terms)} terms on initial auth")


def test_silent_refresh_after_ttl(roster_client):
    """After TTL expires, a second call should refresh silently (no new browser)."""
    # First call — triggers MFA.
    terms1 = roster_client.list_terms()
    assert len(terms1) > 0

    wait = _TEST_TTL_SECONDS + 5
    print(f"\n[WAIT] Sleeping {wait}s for TTL to expire...")
    time.sleep(wait)

    # Second call — should silently refresh, not open a new browser window.
    terms2 = roster_client.list_terms()
    assert len(terms2) > 0, "Expected terms after silent refresh"
    print(f"[OK] Got {len(terms2)} terms after silent refresh")
