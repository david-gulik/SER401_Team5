from __future__ import annotations

from abc import ABC, abstractmethod

from GAVEL.app.dtos.canvas_course import CanvasCourseData


class CanvasClient(ABC):
    @abstractmethod
    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        """Retrieve metadata and modules for a Canvas course."""
        raise NotImplementedError


class UnconfiguredCanvasClient(CanvasClient):
    def __init__(self, message: str = "Canvas not configured") -> None:
        self._message = message

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        raise RuntimeError(self._message)
