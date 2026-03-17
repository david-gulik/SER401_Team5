from __future__ import annotations

from abc import ABC, abstractmethod

from GAVEL.app.dtos.canvas_course import CanvasCourseData
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook


class CanvasClient(ABC):

    @abstractmethod
    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        """Retrieve metadata and modules for a Canvas course."""
        raise NotImplementedError

    @abstractmethod
    def fetch_gradebook(self, course_id: int) -> CanvasGradebook:
        """Retrieve the gradebook for a Canvas course."""
        raise NotImplementedError

    @abstractmethod
    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        """Retrieve the gradebook CSV for a Canvas course."""
        raise NotImplementedError