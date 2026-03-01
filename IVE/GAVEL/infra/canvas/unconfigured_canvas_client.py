from __future__ import annotations

from GAVEL.app.dtos.canvas_course import CanvasCourseData
from GAVEL.app.ports.canvas_client import CanvasClient


class UnconfiguredCanvasClient(CanvasClient):
    def __init__(self, message: str = "Canvas not configured") -> None:
        self._message = message

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        raise RuntimeError(self._message)
