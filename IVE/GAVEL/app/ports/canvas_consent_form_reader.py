from abc import ABC, abstractmethod
from typing import Sequence

from IVE.GAVEL.app.dtos.canvas_consent_form_entry import ConsentFormEntry


class ConsentFormReader(ABC):
    """Defines the contract for loading consent form submissions."""

    @abstractmethod
    def read(self, path: str) -> Sequence[ConsentFormEntry]:
        """Load and return all submission rows from the given file path."""
        ...
