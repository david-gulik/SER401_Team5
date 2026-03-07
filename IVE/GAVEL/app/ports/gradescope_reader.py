from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from GAVEL.app.dtos.gradescope import GradescopeSubmission


class GradescopeReader(ABC):
    @abstractmethod
    def read(self, path: Path) -> List[GradescopeSubmission]:
        """Load a Gradescope YAML export and return submissions."""
        raise NotImplementedError
