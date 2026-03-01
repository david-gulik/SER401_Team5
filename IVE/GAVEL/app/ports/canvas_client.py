from __future__ import annotations

from abc import ABC, abstractmethod

from GAVEL.app.dtos.canvas_course import CanvasCourseData


class CanvasClient(ABC):
    @abstractmethod
    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        """Retrieve metadata and modules for a Canvas course."""
        raise NotImplementedError
