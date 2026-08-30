from __future__ import annotations

from abc import ABC, abstractmethod

from GAVEL.app.dtos.canvas_course import (
    CanvasAssignment,
    CanvasCourse,
    CanvasCourseData,
    CanvasQuiz,
)
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition


class CanvasClient(ABC):
    @abstractmethod
    def list_courses(self) -> list[CanvasCourse]:
        """List courses the authenticated user is enrolled in as a teacher."""
        raise NotImplementedError

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

    @abstractmethod
    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
        """Retrieve the student analysis report
        for a Canvas quiz consent form."""
        raise NotImplementedError

    @abstractmethod
    def list_quizzes(self, course_id: int) -> list[CanvasQuiz]:
        """List quizzes for a Canvas course."""
        raise NotImplementedError

    @abstractmethod
    def list_assignments(self, course_id: int) -> list[CanvasAssignment]:
        """List assignments for a Canvas course."""
        raise NotImplementedError

    @abstractmethod
    def fetch_rubric_assessments(
        self, course_id: int, assignment_id: int
    ) -> list[RubricAssessment]:
        """Retrieve rubric assessments for a Canvas assignment."""
        raise NotImplementedError

    @abstractmethod
    def fetch_rubric_definition(
        self, course_id: int, assignment_id: int
    ) -> RubricDefinition | None:
        """Retrieve the rubric definition (criteria, rating tiers, and point values)
        associated with a Canvas assignment. Returns None if the assignment has no
        associated rubric."""
        raise NotImplementedError
