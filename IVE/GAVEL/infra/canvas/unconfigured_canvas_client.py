from __future__ import annotations

from GAVEL.app.dtos.canvas_course import (
    CanvasAssignment,
    CanvasCourse,
    CanvasCourseData,
    CanvasQuiz,
)
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.app.ports.canvas_client import CanvasClient


class UnconfiguredCanvasClient(CanvasClient):
    def __init__(self, message: str = "Canvas not configured") -> None:
        self._message = message

    def list_courses(self) -> list[CanvasCourse]:
        raise RuntimeError(self._message)

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        raise RuntimeError(self._message)

    def fetch_gradebook(self, course_id: int) -> CanvasGradebook:
        raise RuntimeError(self._message)

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        raise RuntimeError(self._message)

    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
        raise RuntimeError(self._message)

    def list_quizzes(self, course_id: int) -> list[CanvasQuiz]:
        raise RuntimeError(self._message)

    def list_assignments(self, course_id: int) -> list[CanvasAssignment]:
        raise RuntimeError(self._message)

    def fetch_rubric_assessments(
        self, course_id: int, assignment_id: int
    ) -> list[RubricAssessment]:
        raise RuntimeError(self._message)

    def fetch_rubric_definition(
        self, course_id: int, assignment_id: int
    ) -> RubricDefinition | None:
        raise RuntimeError(self._message)
