from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from GAVEL.app.dtos.roster import ClassSection, RosterRequest, TermInfo


class RosterClient(ABC):
    """Port for ASU roster operations: class lookup and roster download."""

    @abstractmethod
    def list_terms(self) -> Sequence[TermInfo]:
        """Return available academic terms."""
        raise NotImplementedError

    @abstractmethod
    def find_sections(
        self,
        term: str,
        subject: str,
        catalog_number: str,
    ) -> Sequence[ClassSection]:
        """Look up sections for a course in a given term."""
        raise NotImplementedError

    @abstractmethod
    def authenticate(self) -> None:
        """Establish an authenticated session (may require user interaction)."""
        raise NotImplementedError

    @abstractmethod
    def fetch_roster(self, request: RosterRequest) -> str:
        """Download roster CSV content for a given term and class number."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release resources (browser sessions, HTTP connections)."""
        raise NotImplementedError
