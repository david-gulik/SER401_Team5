from __future__ import annotations

from GAVEL.app.dtos.canvas_course import CanvasCourse, CanvasCourseData, CanvasModule
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.ports.canvas_client import CanvasClient

# TODO: import DownloadCourseDatasetUseCase once SCRUM-97 is complete

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

COURSE_ID = 253450
QUIZ_ID = 1960789
ASSIGNMENT_IDS = (101, 102)

GRADEBOOK_CSV_BYTES = (
    b"Student,ID,SIS Login ID,Section,Assignment 1 (101)\n"
    b"Points Possible,,,,100\n"
    b"Alice Smith,100001,asmith,Section 1,95\n"
    b"Bob Jones,100002,bjones,Section 1,72\n"
)

# TODO: Add test for gradbook once SCRUM-97 is complete
# TODO: Add tests for consent form once SCRUM-97 is complete
# TODO: Add tests for rubric assessment once SCRUM-97 is complete

# ---------------------------------------------------------------------------
# Reusable MockCanvasClient
# ---------------------------------------------------------------------------


class MockCanvasClient(CanvasClient):
    """
    Configurable mock CanvasClient for use across test suites.
    """

    def __init__(self) -> None:
        self.course_data = CanvasCourseData(
            course=CanvasCourse(id=COURSE_ID, name="IVE Capstone", course_code="TRN-2026Spring"),
            modules=[CanvasModule(id=1, name="Module 0")],
        )

        # TODO: Add gradebook_csv field once SCRUM-97 is complete
        # TODO: Add consent_csv field once SCRUM-97 is complete
        # TODO: Add rubric_assessments field once SCRUM-97 is complete

        # Error injection
        self.fetch_course_data_error: Exception | None = None
        # TODO: Add fetch_gradebook_csv_error field once SCRUM-97 is complete
        # TODO: Add fetch_quiz_error field once SCRUM-97 is complete
        # TODO: Add fetch_rubric_error field once SCRUM-97 is complete

        # Call tracking
        self.fetch_course_data_calls: list[int] = []
        self.fetch_gradebook_calls: list[int] = []
        self.fetch_gradebook_csv_calls: list[int] = []
        self.fetch_quiz_calls: list[tuple[int, int]] = []
        self.fetch_rubric_calls: list[tuple[int, int]] = []

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        self.fetch_course_data_calls.append(course_id)
        if self.fetch_course_data_error:
            raise self.fetch_course_data_error
        return self.course_data

    def fetch_gradebook(self, course_id: int) -> CanvasGradebook:
        self.fetch_gradebook_calls.append(course_id)
        raise NotImplementedError

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        self.fetch_gradebook_csv_calls.append(course_id)
        # TODO: Implement once SCRUM-97 is complete
        raise NotImplementedError

    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
        self.fetch_quiz_calls.append((course_id, quiz_id))
        # TODO: Implement once SCRUM-97 is complete
        raise NotImplementedError

    def fetch_rubric_assessments(
        self, course_id: int, assignment_id: int
    ) -> list[RubricAssessment]:
        self.fetch_rubric_calls.append((course_id, assignment_id))
        # TODO: Implement once SCRUM-97 is complete
        raise NotImplementedError
