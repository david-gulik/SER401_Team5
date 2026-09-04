"""In-memory ports for Download page tests. No network, no browser."""

from __future__ import annotations

from collections.abc import Sequence

from GAVEL.app.dtos.canvas_course import (
    CanvasAssignment,
    CanvasCourse,
    CanvasCourseData,
    CanvasQuiz,
)
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.roster import ClassSection, RosterRequest, TermInfo
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.ports.roster_client import RosterClient


class FakeCanvasClient(CanvasClient):
    """Serves canned lists and records every call.

    Any download-side method appends to ``download_calls`` and raises, so a
    test can prove a download never started.
    """

    def __init__(
        self,
        courses: Sequence[CanvasCourse] = (),
        quizzes: Sequence[CanvasQuiz] = (),
        assignments: Sequence[CanvasAssignment] = (),
    ) -> None:
        self.courses = list(courses)
        self.quizzes = list(quizzes)
        self.assignments = list(assignments)
        self.list_courses_calls = 0
        self.quiz_calls: list[int] = []
        self.assignment_calls: list[int] = []
        self.download_calls: list[str] = []

    def list_courses(self) -> list[CanvasCourse]:
        self.list_courses_calls += 1
        return list(self.courses)

    def list_quizzes(self, course_id: int) -> list[CanvasQuiz]:
        self.quiz_calls.append(course_id)
        return list(self.quizzes)

    def list_assignments(self, course_id: int) -> list[CanvasAssignment]:
        self.assignment_calls.append(course_id)
        return list(self.assignments)

    def _unexpected(self, name: str) -> None:
        self.download_calls.append(name)
        raise AssertionError(f"{name} should not have been called")

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        self._unexpected("fetch_course_data")
        raise AssertionError  # unreachable, keeps the return type honest

    def fetch_gradebook(self, course_id: int) -> CanvasGradebook:
        self._unexpected("fetch_gradebook")
        raise AssertionError

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        self._unexpected("fetch_gradebook_csv")
        raise AssertionError

    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
        self._unexpected("fetch_quiz_student_analysis")
        raise AssertionError

    def fetch_rubric_assessments(
        self, course_id: int, assignment_id: int
    ) -> list[RubricAssessment]:
        self._unexpected("fetch_rubric_assessments")
        raise AssertionError

    def fetch_rubric_definition(
        self, course_id: int, assignment_id: int
    ) -> RubricDefinition | None:
        self._unexpected("fetch_rubric_definition")
        raise AssertionError


class FakeRosterClient(RosterClient):
    def list_terms(self) -> Sequence[TermInfo]:
        return []

    def find_sections(self, term: str, subject: str, catalog_number: str) -> Sequence[ClassSection]:
        return []

    def authenticate(self) -> None:
        pass

    def fetch_roster(self, request: RosterRequest) -> str:
        return ""

    def close(self) -> None:
        pass
