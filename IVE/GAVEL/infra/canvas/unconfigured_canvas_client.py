from __future__ import annotations

from GAVEL.app.dtos.canvas_course import CanvasCourseData
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook


class UnconfiguredCanvasClient(CanvasClient):
    def __init__(self, message: str = "Canvas not configured") -> None:
        self._message = message

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        raise RuntimeError(self._message)

    def fetch_gradebook(self, course_id: int) -> CanvasGradebook:
        raise RuntimeError(self._message)

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        raise RuntimeError(self._message)
    
    def fetch_quiz_student_analysis(
            self, course_id: int, quiz_id: int) -> bytes:
        