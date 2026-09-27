from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from GAVEL.app.dtos.rubric_definition import RubricDefinition


class RubricDefinitionReader(ABC):
    """Defines the contract for loading a saved rubric definition."""

    @abstractmethod
    def read(self, path: Path) -> RubricDefinition:
        """Load a ``rubric_definition.json`` file (criteria, ratings, point values)."""
        raise NotImplementedError
