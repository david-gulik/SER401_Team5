from __future__ import annotations

import pytest

from GAVEL.app.dtos.roster import RosterRequest
from GAVEL.infra.roster.unconfigured_roster_client import UnconfiguredRosterClient


def test_reports_itself_as_unconfigured():
    assert UnconfiguredRosterClient().is_configured is False


def test_every_operation_raises_the_configured_message():
    client = UnconfiguredRosterClient("set it up")
    with pytest.raises(RuntimeError, match="set it up"):
        client.list_terms()
    with pytest.raises(RuntimeError, match="set it up"):
        client.find_sections("2267", "SER", "401")
    with pytest.raises(RuntimeError, match="set it up"):
        client.authenticate()
    with pytest.raises(RuntimeError, match="set it up"):
        client.fetch_roster(RosterRequest(term="2267", class_number="12345"))
    client.close()  # never raises
