from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from GAVEL.app.dtos.rubric_assessment import RubricAssessment


class RubricAssessmentReader(ABC):
    """Defines the contract for loading saved rubric assessments."""

    @abstractmethod
    def read(self, path: Path) -> tuple[RubricAssessment, ...]:
        """Load a ``rubric_assessments.json`` file and return one entry per graded submission."""
        raise NotImplementedError
