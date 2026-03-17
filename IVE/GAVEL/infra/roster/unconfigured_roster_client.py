from __future__ import annotations

from typing import Sequence

from GAVEL.app.dtos.roster import ClassSection, RosterRequest, TermInfo
from GAVEL.app.ports.roster_client import RosterClient


class UnconfiguredRosterClient(RosterClient):
    """Placeholder used when roster features are disabled or not configured."""

    def __init__(
        self,
        message: str = (
            "ASU Roster is not configured. "
            "Set ROSTER_AUTH_METHOD to 'selenium' or 'cookies' to enable."
        ),
    ) -> None:
        self._message = message

    def list_terms(self) -> Sequence[TermInfo]:
        raise RuntimeError(self._message)

    def find_sections(
        self, term: str, subject: str, catalog_number: str,
    ) -> Sequence[ClassSection]:
        raise RuntimeError(self._message)

    def authenticate(self) -> None:
        raise RuntimeError(self._message)

    def fetch_roster(self, request: RosterRequest) -> str:
        raise RuntimeError(self._message)

    def close(self) -> None:
        pass
