from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from GAVEL.app.dtos.gradescope import GradescopeSubmission


class GradescopeReader(ABC):
    @abstractmethod
    def read(self, path: Path) -> list[GradescopeSubmission]:
        """Load a Gradescope YAML export and return submissions."""
        raise NotImplementedError
