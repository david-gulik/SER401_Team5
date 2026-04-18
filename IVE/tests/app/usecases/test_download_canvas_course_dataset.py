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
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.download_course_dataset import (
    DownloadCourseDatasetRequest,
    DownloadCourseDatasetUseCase,
)

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

        # Error injection
        self.fetch_course_data_error: Exception | None = None
        self.fetch_gradebook_csv_error: Exception | None = None
        self.fetch_quiz_error: Exception | None = None
        self.fetch_rubric_error: Exception | None = None

        # Call tracking
        self.fetch_course_data_calls: list[int] = []
        self.fetch_gradebook_calls: list[int] = []
        self.fetch_gradebook_csv_calls: list[int] = []
        self.fetch_quiz_calls: list[tuple[int, int]] = []
        self.fetch_rubric_calls: list[tuple[int, int]] = []

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

    def fetch_rubric_assessments(
        self, course_id: int, assignment_id: int
    ) -> list[RubricAssessment]:
        self.fetch_rubric_calls.append((course_id, assignment_id))
        if self.fetch_rubric_error:
            raise self.fetch_rubric_error
        return self.rubric_assessments


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
def request_(tmp_path: Path) -> DownloadCourseDatasetRequest:
    return DownloadCourseDatasetRequest(
        course_id=COURSE_ID,
        quiz_id=QUIZ_ID,
        assignment_ids=ASSIGNMENT_IDS,
        output_dir=tmp_path,
    )


# ---------------------------------------------------------------------------
# Gradebook CSV happy path + API error tests
# ---------------------------------------------------------------------------


class TestGradebookHappyPath:
    def test_execute_returns_result(self, use_case, request_):
        result = use_case.execute(request_)
        assert result is not None

    def test_dataset_dir_is_created(self, use_case, request_):
        result = use_case.execute(request_)
        assert result.dataset_path.exists()

    def test_dataset_dir_name_contains_course_id(self, use_case, request_):
        result = use_case.execute(request_)
        assert str(COURSE_ID) in result.dataset_path.name

    def test_gradebook_csv_is_written(self, use_case, request_):
        result = use_case.execute(request_)
        assert (result.dataset_path / "gradebook.csv").exists()

    def test_gradebook_csv_content_matches(self, use_case, request_):
        result = use_case.execute(request_)
        assert (result.dataset_path / "gradebook.csv").read_bytes() == GRADEBOOK_CSV_BYTES

    def test_gradebook_fetched_with_correct_course_id(self, use_case, request_, client):
        use_case.execute(request_)
        assert COURSE_ID in client.fetch_gradebook_csv_calls

    def test_result_message_contains_course_id(self, use_case, request_):
        result = use_case.execute(request_)
        assert str(COURSE_ID) in result.message

    def test_manifest_is_written(self, use_case, request_):
        result = use_case.execute(request_)
        assert (result.dataset_path / "dataset_manifest.json").exists()

    def test_manifest_references_gradebook_csv(self, use_case, request_):
        result = use_case.execute(request_)
        data = json.loads((result.dataset_path / "dataset_manifest.json").read_text())
        assert data["gradebook_csv"] == "gradebook.csv"

    def test_manifest_contains_course_id(self, use_case, request_):
        result = use_case.execute(request_)
        data = json.loads((result.dataset_path / "dataset_manifest.json").read_text())
        assert data["course_id"] == COURSE_ID

    def test_manifest_contains_generated_at(self, use_case, request_):
        result = use_case.execute(request_)
        data = json.loads((result.dataset_path / "dataset_manifest.json").read_text())
        assert "generated_at" in data


class TestGradebookApiErrors:
    def test_timeout_on_gradebook_propagates(self, use_case, request_, client):
        client.fetch_gradebook_csv_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError, match="network timeout"):
            use_case.execute(request_)

    def test_unauthorized_on_gradebook_propagates(self, use_case, request_, client):
        client.fetch_gradebook_csv_error = PermissionError("401 Unauthorized")
        with pytest.raises(PermissionError, match="401"):
            use_case.execute(request_)

    def test_no_manifest_written_on_gradebook_error(self, use_case, request_, client, tmp_path):
        client.fetch_gradebook_csv_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError):
            use_case.execute(request_)
        assert not any(tmp_path.rglob("dataset_manifest.json"))


# ---------------------------------------------------------------------------
# Consent form CSV happy path + missing consent form error tests
# ---------------------------------------------------------------------------


class TestConsentFormHappyPath:
    def test_consent_form_csv_is_written(self, use_case, request_):
        result = use_case.execute(request_)
        assert (result.dataset_path / "consent_form.csv").exists()

    def test_consent_form_csv_content_matches(self, use_case, request_):
        result = use_case.execute(request_)
        assert (result.dataset_path / "consent_form.csv").read_bytes() == CONSENT_CSV_BYTES

    def test_quiz_fetched_with_correct_ids(self, use_case, request_, client):
        use_case.execute(request_)
        assert (COURSE_ID, QUIZ_ID) in client.fetch_quiz_calls

    def test_manifest_references_consent_form_csv(self, use_case, request_):
        result = use_case.execute(request_)
        data = json.loads((result.dataset_path / "dataset_manifest.json").read_text())
        assert data["consent_form_csv"] == "consent_form.csv"

    def test_consent_csv_has_leave_blank_if_column(self, use_case, request_):
        """Verify the consent CSV contains the column palantir's find_consented searches for."""
        result = use_case.execute(request_)
        csv_text = (result.dataset_path / "consent_form.csv").read_bytes().decode()
        assert "leave blank if" in csv_text.splitlines()[0]

    def test_consent_csv_has_do_you_consent_column(self, use_case, request_):
        """Verify the consent CSV contains the column palantir's find_consented searches for."""
        result = use_case.execute(request_)
        csv_text = (result.dataset_path / "consent_form.csv").read_bytes().decode()
        assert "Do you consent" in csv_text.splitlines()[0]


class TestMissingConsentForm:
    def test_raises_when_quiz_not_found(self, use_case, request_, client):
        client.consent_csv = None
        with pytest.raises(FileNotFoundError):
            use_case.execute(request_)

    def test_error_message_contains_quiz_id(self, use_case, request_, client):
        client.consent_csv = None
        with pytest.raises(FileNotFoundError) as exc_info:
            use_case.execute(request_)
        assert str(QUIZ_ID) in str(exc_info.value)

    def test_error_message_contains_course_id(self, use_case, request_, client):
        client.consent_csv = None
        with pytest.raises(FileNotFoundError) as exc_info:
            use_case.execute(request_)
        assert str(COURSE_ID) in str(exc_info.value)

    def test_quiz_fetch_was_attempted(self, use_case, request_, client):
        client.consent_csv = None
        with pytest.raises(FileNotFoundError):
            use_case.execute(request_)
        assert len(client.fetch_quiz_calls) == 1

    def test_timeout_on_quiz_fetch_propagates(self, use_case, request_, client):
        client.fetch_quiz_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError, match="network timeout"):
            use_case.execute(request_)

    def test_unauthorized_on_quiz_fetch_propagates(self, use_case, request_, client):
        client.fetch_quiz_error = PermissionError("401 Unauthorized")
        with pytest.raises(PermissionError, match="401"):
            use_case.execute(request_)

    def test_no_manifest_written_on_quiz_error(self, use_case, request_, client, tmp_path):
        client.fetch_quiz_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError):
            use_case.execute(request_)
        assert not any(tmp_path.rglob("dataset_manifest.json"))


# ---------------------------------------------------------------------------
# Rubric assessments happy path + empty rubric + API errors
# ---------------------------------------------------------------------------


class TestRubricHappyPath:
    def test_rubric_dir_is_created(self, use_case, request_):
        result = use_case.execute(request_)
        assert (result.dataset_path / "rubric_assessments").exists()

    def test_rubric_json_written_per_assignment(self, use_case, request_):
        result = use_case.execute(request_)
        for assignment_id in ASSIGNMENT_IDS:
            assert (
                result.dataset_path / "rubric_assessments" / f"assignment_{assignment_id}.json"
            ).exists()

    def test_rubric_json_is_valid_json(self, use_case, request_):
        result = use_case.execute(request_)
        for assignment_id in ASSIGNMENT_IDS:
            rubric = result.dataset_path / "rubric_assessments" / f"assignment_{assignment_id}.json"
            assert isinstance(json.loads(rubric.read_text()), list)

    def test_rubric_json_contains_student_id(self, use_case, request_):
        result = use_case.execute(request_)
        rubric = result.dataset_path / "rubric_assessments" / f"assignment_{ASSIGNMENT_IDS[0]}.json"
        data = json.loads(rubric.read_text())
        assert all("student_id" in entry for entry in data)

    def test_rubric_json_contains_criteria(self, use_case, request_):
        result = use_case.execute(request_)
        rubric = result.dataset_path / "rubric_assessments" / f"assignment_{ASSIGNMENT_IDS[0]}.json"
        data = json.loads(rubric.read_text())
        assert all("criteria" in entry for entry in data)

    def test_rubric_fetched_for_each_assignment(self, use_case, request_, client):
        use_case.execute(request_)
        fetched_assignment_ids = [aid for _, aid in client.fetch_rubric_calls]
        for assignment_id in ASSIGNMENT_IDS:
            assert assignment_id in fetched_assignment_ids

    def test_manifest_references_all_rubric_files(self, use_case, request_):
        result = use_case.execute(request_)
        data = json.loads((result.dataset_path / "dataset_manifest.json").read_text())
        assert len(data["rubric_assessments"]) == len(ASSIGNMENT_IDS)

    def test_manifest_rubric_paths_use_subdirectory(self, use_case, request_):
        result = use_case.execute(request_)
        data = json.loads((result.dataset_path / "dataset_manifest.json").read_text())
        for path in data["rubric_assessments"]:
            assert path.startswith("rubric_assessments/")


class TestEmptyRubricAssessments:
    def test_rubric_json_is_empty_list_when_no_assessments(self, use_case, request_, client):
        client.rubric_assessments = []
        result = use_case.execute(request_)
        for assignment_id in ASSIGNMENT_IDS:
            rubric = result.dataset_path / "rubric_assessments" / f"assignment_{assignment_id}.json"
            assert json.loads(rubric.read_text()) == []

    def test_manifest_still_references_rubric_files(self, use_case, request_, client):
        client.rubric_assessments = []
        result = use_case.execute(request_)
        data = json.loads((result.dataset_path / "dataset_manifest.json").read_text())
        assert len(data["rubric_assessments"]) == len(ASSIGNMENT_IDS)

    def test_gradebook_and_consent_still_written(self, use_case, request_, client):
        client.rubric_assessments = []
        result = use_case.execute(request_)
        assert (result.dataset_path / "gradebook.csv").exists()
        assert (result.dataset_path / "consent_form.csv").exists()


class TestRubricApiErrors:
    def test_timeout_on_rubric_fetch_propagates(self, use_case, request_, client):
        client.fetch_rubric_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError, match="network timeout"):
            use_case.execute(request_)

    def test_unauthorized_on_rubric_fetch_propagates(self, use_case, request_, client):
        client.fetch_rubric_error = PermissionError("401 Unauthorized")
        with pytest.raises(PermissionError, match="401"):
            use_case.execute(request_)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_raises_for_zero_course_id(self, use_case, tmp_path):
        request_ = DownloadCourseDatasetRequest(
            course_id=0,
            quiz_id=QUIZ_ID,
            assignment_ids=ASSIGNMENT_IDS,
            output_dir=tmp_path,
        )
        with pytest.raises(ValueError, match="course_id must be greater than zero"):
            use_case.execute(request_)

    def test_raises_for_negative_course_id(self, use_case, tmp_path):
        request_ = DownloadCourseDatasetRequest(
            course_id=-1,
            quiz_id=QUIZ_ID,
            assignment_ids=ASSIGNMENT_IDS,
            output_dir=tmp_path,
        )
        with pytest.raises(ValueError, match="course_id must be greater than zero"):
            use_case.execute(request_)

    def test_client_not_called_for_invalid_request(self, use_case, tmp_path, client):
        request_ = DownloadCourseDatasetRequest(
            course_id=0,
            quiz_id=QUIZ_ID,
            assignment_ids=ASSIGNMENT_IDS,
            output_dir=tmp_path,
        )
        with pytest.raises(ValueError):
            use_case.execute(request_)
        assert client.fetch_gradebook_csv_calls == []
        assert client.fetch_quiz_calls == []
        assert client.fetch_rubric_calls == []


# ---------------------------------------------------------------------------
# MockCanvasClient reusability
# ---------------------------------------------------------------------------


class TestMockCanvasClientReusability:
    def test_is_subclass_of_canvas_client(self):
        assert issubclass(MockCanvasClient, CanvasClient)

    def test_returns_gradebook_csv(self):
        client = MockCanvasClient()
        assert client.fetch_gradebook_csv(COURSE_ID) == GRADEBOOK_CSV_BYTES

    def test_returns_consent_csv(self):
        client = MockCanvasClient()
        assert client.fetch_quiz_student_analysis(COURSE_ID, QUIZ_ID) == CONSENT_CSV_BYTES

    def test_returns_rubric_assessments(self):
        client = MockCanvasClient()
        result = client.fetch_rubric_assessments(COURSE_ID, ASSIGNMENT_IDS[0])
        assert isinstance(result, list)
        assert all(isinstance(r, RubricAssessment) for r in result)

    def test_tracks_quiz_calls(self):
        client = MockCanvasClient()
        client.fetch_quiz_student_analysis(COURSE_ID, QUIZ_ID)
        client.fetch_quiz_student_analysis(COURSE_ID, QUIZ_ID)
        assert len(client.fetch_quiz_calls) == 2

    def test_custom_gradebook_csv(self):
        client = MockCanvasClient()
        client.gradebook_csv = b"custom,csv\n1,2\n"
        assert client.fetch_gradebook_csv(COURSE_ID) == b"custom,csv\n1,2\n"

    def test_injected_error_raises(self):
        client = MockCanvasClient()
        client.fetch_quiz_error = RuntimeError("Canvas is down")
        with pytest.raises(RuntimeError, match="Canvas is down"):
            client.fetch_quiz_student_analysis(COURSE_ID, QUIZ_ID)
