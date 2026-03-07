from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from GAVEL.app.dtos.canvas_course import CanvasCourseData
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook


class CanvasClient(ABC):

    @abstractmethod
    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        """Retrieve metadata and modules for a Canvas course."""
        raise NotImplementedError

    @abstractmethod
    def fetch_gradebook(self, path: Path) -> CanvasGradebook:
        """
        Parse a Canvas gradebook CSV export from a local file path.

        The Canvas gradebook export is a 3-row-preamble CSV file. This method
        handles preamble skipping, assignment column detection, and filtering
        of sentinel/test rows. The caller provides the path to the downloaded
        CSV; acquisition (download vs. local file) is the adapter's concern.
        """
        raise NotImplementedError
