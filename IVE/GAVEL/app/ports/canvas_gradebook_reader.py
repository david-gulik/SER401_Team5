from abc import ABC, abstractmethod

from IVE.GAVEL.app.dtos.canvas_gradebook import CanvasGradebook


class GradebookReader(ABC):
    """Defines the contract for loading Canvas gradebook data."""

    @abstractmethod
    def read(self, path: str) -> CanvasGradebook:
        """Load and return all submission rows from the given file path."""
        ...
