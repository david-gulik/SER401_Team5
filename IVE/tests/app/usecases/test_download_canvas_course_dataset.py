"""
Unit tests for DownloadCourseDatasetUseCase using a mock CanvasClient.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse, CanvasCourseData, CanvasModule
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.rubric_assessment import RubricAssessment, RubricCriterionScore
from GAVEL.app.dtos.rubric_definition import (
    RubricCriterionDefinition,
    RubricDefinition,
    RubricRating,
)
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.download_course_dataset import (
    DownloadCourseDatasetRequest,
    DownloadCourseDatasetUseCase,
)
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import load_manifest

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

COURSE_ID = 253450
QUIZ_ID = 1960789
ASSIGNMENT_IDS = [101, 102]

# Matches real Canvas gradebook CSV export format:
# - Column names from GradebookStudentRow DTO (Student, ID, SIS Login ID, section)
# - Assignment column format: "<Module>: <Name> (<canvas_assignment_id>)"
# - Row 2 is blank (preamble), Row 3 is Points Possible
GRADEBOOK_CSV_BYTES = (
    b"Student,ID,SIS Login ID,section,Module 1: Assignment 1 (101),Module 1: Assignment 2 (102)\n"
    b"Points Possible,,,, 100, 100\n"
    b'"Crain, Lindy",494030,asurite1,TRN-2026Spring-IVECapstone,95,88\n'
    b'"Bourque, Bailey",309780,asurite2,TRN-2026Spring-IVECapstone,72,65\n'
)

# Matches real Canvas quiz student analysis CSV export format.
# Question columns include the Canvas question ID prefix.
# The "leave blank if" and "Do you consent" substrings are what
# palantir's find_consented searches for dynamically.
CONSENT_CSV_BYTES = (
    b"name,id,sis_id,section,section_id,section_sis_id,submitted,attempt,"
    b'"29684859: Name: (leave blank if you do not consent)",0.0,'
    b'"29684860: Do you consent to be included in the study?",0.0,'
    b"n correct,n incorrect,score\n"
    b"Lindy Crain,494030,1219749063,TRN-2026Spring-IVECapstone,385739,"
    b"TRN-2026Spring-1770947129529_section_main,2026-04-09 03:28:49 UTC,1,"
    b"Lindy Crain,0.0,True,0.0,2,0,0.0\n"
    b"Bailey Bourque,309780,1217482318,TRN-2026Spring-IVECapstone,385739,"
    b"TRN-2026Spring-1770947129529_section_main,2026-04-07 00:51:23 UTC,1,"
    b"Bailey Bourque,0.0,True,0.0,2,0,0.0\n"
)

# RubricAssessment and RubricCriterionScore match their DTOs exactly:
# RubricAssessment(student_id: int, submission_id: int, criteria: tuple[RubricCriterionScore, ...])
# RubricCriterionScore(criterion_id: str, points: float | None, comments: str)
RUBRIC_ASSESSMENTS = [
    RubricAssessment(
        student_id=100001,
        submission_id=9001,
        criteria=(RubricCriterionScore(criterion_id="crit_1", points=4.0, comments="Good work"),),
    ),
    RubricAssessment(
        student_id=100002,
        submission_id=9002,
        criteria=(
            RubricCriterionScore(criterion_id="crit_1", points=3.0, comments="Needs improvement"),
        ),
    ),
]

RUBRIC_DEFINITION = RubricDefinition(
    rubric_id="rub_1",
    title="Problem Set Rubric",
    points_possible=4.0,
    free_form_criterion_comments=False,
    criteria=(
        RubricCriterionDefinition(
            id="crit_1",
            description="Correctness",
            long_description="",
            points=4.0,
            ratings=(RubricRating(id="r1", description="Full", long_description="", points=4.0),),
        ),
    ),
)


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
        self.gradebook_csv: bytes = GRADEBOOK_CSV_BYTES
        self.consent_csv: bytes | None = CONSENT_CSV_BYTES
        self.rubric_assessments: list[RubricAssessment] = RUBRIC_ASSESSMENTS
        self.rubric_definition: RubricDefinition | None = RUBRIC_DEFINITION

        # Error injection
        self.fetch_course_data_error: Exception | None = None
        self.fetch_gradebook_csv_error: Exception | None = None
        self.fetch_quiz_error: Exception | None = None
        self.fetch_rubric_error: Exception | None = None
        self.fetch_rubric_definition_error: Exception | None = None

        # Call tracking
        self.fetch_course_data_calls: list[int] = []
        self.fetch_gradebook_calls: list[int] = []
        self.fetch_gradebook_csv_calls: list[int] = []
        self.fetch_quiz_calls: list[tuple[int, int]] = []
        self.fetch_rubric_calls: list[tuple[int, int]] = []
        self.fetch_rubric_definition_calls: list[tuple[int, int]] = []

    def list_courses(self) -> list:
        return []

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
        if self.fetch_gradebook_csv_error:
            raise self.fetch_gradebook_csv_error
        return self.gradebook_csv

    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
        self.fetch_quiz_calls.append((course_id, quiz_id))
        if self.fetch_quiz_error:
            raise self.fetch_quiz_error
        if self.consent_csv is None:
            raise FileNotFoundError(f"Quiz {quiz_id} not found in course {course_id}")
        return self.consent_csv

    def list_quizzes(self, course_id: int) -> list:
        return []

    def list_assignments(self, course_id: int) -> list:
        return []

    def fetch_rubric_assessments(
        self, course_id: int, assignment_id: int
    ) -> list[RubricAssessment]:
        self.fetch_rubric_calls.append((course_id, assignment_id))
        if self.fetch_rubric_error:
            raise self.fetch_rubric_error
        return self.rubric_assessments

    def fetch_rubric_definition(
        self, course_id: int, assignment_id: int
    ) -> RubricDefinition | None:
        self.fetch_rubric_definition_calls.append((course_id, assignment_id))
        if self.fetch_rubric_definition_error:
            raise self.fetch_rubric_definition_error
        return self.rubric_definition


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> MockCanvasClient:
    return MockCanvasClient()


@pytest.fixture
def use_case(client: MockCanvasClient) -> DownloadCourseDatasetUseCase:
    return DownloadCourseDatasetUseCase(canvas_client=client)


@pytest.fixture
def folder(tmp_path: Path) -> CourseFolder:
    return Workspace(tmp_path).course(CourseKey.parse("ser222_25sc_12345"))


@pytest.fixture
def request_(folder: CourseFolder) -> DownloadCourseDatasetRequest:
    return DownloadCourseDatasetRequest(
        course_id=COURSE_ID,
        quiz_id=QUIZ_ID,
        assignment_ids=ASSIGNMENT_IDS,
        folder=folder,
    )


def statuses(result) -> dict[str, str]:
    return {o.step: o.status for o in result.outcomes}


# ---------------------------------------------------------------------------
# Happy path: everything lands in one course folder and one manifest
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_every_step_succeeds(self, use_case, request_):
        result = use_case.execute(request_)
        assert set(statuses(result).values()) == {"succeeded"}
        assert [o.step for o in result.outcomes] == [
            "course metadata",
            "gradebook",
            "consent form",
            "rubric 101",
            "rubric 102",
        ]
        assert result.failed == () and result.already_downloaded == ()

    def test_files_land_in_the_original_tree(self, use_case, request_, folder):
        use_case.execute(request_)
        original = folder.original
        assert original.gradebook_csv.read_bytes() == GRADEBOOK_CSV_BYTES
        assert original.consent_form_csv.read_bytes() == CONSENT_CSV_BYTES
        for assignment_id in ASSIGNMENT_IDS:
            assignment = original.find_assignment(assignment_id)
            assert assignment is not None
            assert isinstance(json.loads(assignment.rubric_assessments_json.read_text()), list)
            assert assignment.rubric_definition_json.exists()

    def test_result_points_at_the_folder(self, use_case, request_, folder):
        result = use_case.execute(request_)
        assert result.folder == folder
        assert str(COURSE_ID) in result.message
        assert "5 saved" in result.message

    def test_fetches_use_the_requested_ids(self, use_case, request_, client):
        use_case.execute(request_)
        assert client.fetch_course_data_calls == [COURSE_ID]
        assert client.fetch_gradebook_csv_calls == [COURSE_ID]
        assert client.fetch_quiz_calls == [(COURSE_ID, QUIZ_ID)]
        assert [aid for _, aid in client.fetch_rubric_calls] == ASSIGNMENT_IDS
        assert [aid for _, aid in client.fetch_rubric_definition_calls] == ASSIGNMENT_IDS

    def test_one_manifest_describes_everything(self, use_case, request_, folder):
        use_case.execute(request_)
        manifest = load_manifest(folder.manifest_path)
        assert manifest.canvas_course_id == COURSE_ID
        assert manifest.canvas_course_name == "IVE Capstone"
        assert [m.name for m in manifest.modules] == ["Module 0"]
        assert {a.kind for a in manifest.artifacts} == {
            "gradebook",
            "consent_form",
            "rubric_assessments",
            "rubric_definition",
        }
        assert [a.canvas_id for a in manifest.assignments] == ASSIGNMENT_IDS
        assert not (folder.path / "dataset_manifest.json").exists()

    def test_no_assignments_skips_rubrics(self, use_case, folder, client):
        result = use_case.execute(
            DownloadCourseDatasetRequest(
                course_id=COURSE_ID, quiz_id=QUIZ_ID, assignment_ids=[], folder=folder
            )
        )
        assert [o.step for o in result.outcomes] == ["course metadata", "gradebook", "consent form"]
        assert client.fetch_rubric_calls == []


# ---------------------------------------------------------------------------
# Steps are independent
# ---------------------------------------------------------------------------


class TestPartialFailure:
    def test_gradebook_error_does_not_stop_the_rest(self, use_case, request_, client, folder):
        client.fetch_gradebook_csv_error = TimeoutError("network timeout")
        result = use_case.execute(request_)
        assert statuses(result)["gradebook"] == "failed"
        assert "network timeout" in result.failed[0].detail
        assert statuses(result)["consent form"] == "succeeded"
        assert folder.original.consent_form_csv.exists()
        assert not folder.original.gradebook_csv.exists()

    def test_missing_consent_form_is_reported(self, use_case, request_, client):
        client.consent_csv = None
        result = use_case.execute(request_)
        assert statuses(result)["consent form"] == "failed"
        assert str(QUIZ_ID) in result.failed[0].detail

    def test_rubric_error_is_scoped_to_its_assignment(self, use_case, request_, client):
        client.fetch_rubric_error = PermissionError("401 Unauthorized")
        result = use_case.execute(request_)
        assert statuses(result)["rubric 101"] == "failed"
        assert statuses(result)["rubric 102"] == "failed"
        assert statuses(result)["gradebook"] == "succeeded"

    def test_course_metadata_error_is_reported(self, use_case, request_, client):
        client.fetch_course_data_error = RuntimeError("no such course")
        result = use_case.execute(request_)
        assert statuses(result)["course metadata"] == "failed"
        assert statuses(result)["gradebook"] == "succeeded"

    def test_assignment_without_rubric_still_records_assessments(
        self, use_case, request_, client, folder
    ):
        client.rubric_definition = None
        use_case.execute(request_)
        for assignment_id in ASSIGNMENT_IDS:
            assignment = folder.original.find_assignment(assignment_id)
            assert assignment is not None
            assert assignment.rubric_assessments_json.exists()
            assert not assignment.rubric_definition_json.exists()


# ---------------------------------------------------------------------------
# Re-running
# ---------------------------------------------------------------------------


class TestAlreadyDownloaded:
    def test_second_run_downloads_nothing_new(self, use_case, request_, client):
        use_case.execute(request_)
        fetched = len(client.fetch_gradebook_csv_calls)
        result = use_case.execute(request_)
        assert statuses(result)["gradebook"] == "already_downloaded"
        assert statuses(result)["consent form"] == "already_downloaded"
        assert statuses(result)["rubric 101"] == "already_downloaded"
        assert statuses(result)["course metadata"] == "succeeded"  # metadata is always refreshed
        assert len(client.fetch_gradebook_csv_calls) == fetched
        assert "4 already downloaded" in result.message

    def test_overwrite_downloads_everything_again(self, use_case, request_, folder):
        use_case.execute(request_)
        result = use_case.execute(
            DownloadCourseDatasetRequest(
                course_id=COURSE_ID,
                quiz_id=QUIZ_ID,
                assignment_ids=ASSIGNMENT_IDS,
                folder=folder,
                overwrite=True,
            )
        )
        assert set(statuses(result).values()) == {"succeeded"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    @pytest.mark.parametrize(
        ("course_id", "quiz_id"), [(0, QUIZ_ID), (-1, QUIZ_ID), (COURSE_ID, 0)]
    )
    def test_invalid_ids_raise_before_any_fetch(self, use_case, folder, client, course_id, quiz_id):
        with pytest.raises(ValueError, match="must be greater than zero"):
            use_case.execute(
                DownloadCourseDatasetRequest(
                    course_id=course_id,
                    quiz_id=quiz_id,
                    assignment_ids=ASSIGNMENT_IDS,
                    folder=folder,
                )
            )
        assert client.fetch_gradebook_csv_calls == []
        assert client.fetch_quiz_calls == []
        assert client.fetch_rubric_calls == []
