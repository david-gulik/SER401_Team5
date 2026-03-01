from abc import ABC, abstractmethod
from typing import Sequence

from GAVEL.app.dtos.consent_form_entry import ConsentFormEntry


class ConsentFormReader(ABC):
    """Defines the contract for loading consent form submissions."""

    @abstractmethod
    def load(self, path: str) -> Sequence[ConsentFormEntry]:
        """Load and return all submission rows from the given file path."""
        ...
