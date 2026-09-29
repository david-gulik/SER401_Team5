from __future__ import annotations

import json
from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasCourseData
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.rubric_assessment import RubricAssessment, RubricCriterionScore
from GAVEL.app.dtos.rubric_definition import (
    RubricCriterionDefinition,
    RubricDefinition,
    RubricRating,
)
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.download_rubric_assessment import (
    DownloadRubricAssessmentRequest,
    DownloadRubricAssessmentUseCase,
)
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import load_manifest
from GAVEL.app.workspace.recording import ArtifactExistsError

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

COURSE_ID = 253450
ASSIGNMENT_ID = 7216983
ASSIGNMENT = CanvasAssignment(id=ASSIGNMENT_ID, name="Mod 4: ADJ Problem Set")

RUBRIC_ASSESSMENTS = [
    RubricAssessment(
        student_id=100001,
        submission_id=9001,
        criteria=(
            RubricCriterionScore(criterion_id="crit_1", points=4.0, comments="Good work"),
            RubricCriterionScore(criterion_id="crit_2", points=2.0, comments=""),
        ),
    ),
    RubricAssessment(
        student_id=100002,
        submission_id=9002,
        criteria=(
            RubricCriterionScore(criterion_id="crit_1", points=3.0, comments="Needs improvement"),
            RubricCriterionScore(criterion_id="crit_2", points=1.0, comments=""),
        ),
    ),
]

RUBRIC_DEFINITION = RubricDefinition(
    rubric_id="rub_1",
    title="Problem Set Rubric",
    points_possible=6.0,
    free_form_criterion_comments=False,
    criteria=(
        RubricCriterionDefinition(
            id="crit_1",
            description="Correctness",
            long_description="",
            points=4.0,
            ratings=(
                RubricRating(id="r1", description="Full", long_description="", points=4.0),
                RubricRating(id="r2", description="None", long_description="", points=0.0),
            ),
        ),
        RubricCriterionDefinition(
            id="crit_2",
            description="Clarity",
            long_description="",
            points=2.0,
            ratings=(),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------


class MockCanvasClient(CanvasClient):
    def __init__(self) -> None:
        self.rubric_assessments: list[RubricAssessment] = RUBRIC_ASSESSMENTS
        self.rubric_definition: RubricDefinition | None = RUBRIC_DEFINITION
        self.fetch_rubric_error: Exception | None = None
        self.fetch_rubric_definition_error: Exception | None = None
        self.fetch_rubric_calls: list[tuple[int, int]] = []
        self.fetch_rubric_definition_calls: list[tuple[int, int]] = []

    def list_courses(self) -> list:
        return []

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        raise NotImplementedError

    def fetch_gradebook(self, course_id: int) -> CanvasGradebook:
        raise NotImplementedError

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        raise NotImplementedError

    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
        raise NotImplementedError

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
def use_case(client: MockCanvasClient) -> DownloadRubricAssessmentUseCase:
    return DownloadRubricAssessmentUseCase(canvas_client=client)


@pytest.fixture
def folder(tmp_path: Path) -> CourseFolder:
    return Workspace(tmp_path).course(CourseKey.parse("ser222_25sc_12345"))


@pytest.fixture
def request_(folder: CourseFolder) -> DownloadRubricAssessmentRequest:
    return DownloadRubricAssessmentRequest(
        course_id=COURSE_ID, assignment=ASSIGNMENT, folder=folder
    )


@pytest.fixture
def assessments_path(folder: CourseFolder) -> Path:
    return folder.original.assignment(ASSIGNMENT_ID, 4).rubric_assessments_json


@pytest.fixture
def definition_path(folder: CourseFolder) -> Path:
    return folder.original.assignment(ASSIGNMENT_ID, 4).rubric_definition_json


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_execute_returns_result(self, use_case, request_):
        result = use_case.execute(request_)
        assert result is not None

    def test_output_file_is_created(self, use_case, request_, assessments_path):
        use_case.execute(request_)
        expected = assessments_path
        assert expected.exists()

    def test_output_is_valid_json(self, use_case, request_, assessments_path):
        use_case.execute(request_)
        path = assessments_path
        assert isinstance(json.loads(path.read_text()), list)

    def test_output_contains_student_id(self, use_case, request_, assessments_path):
        use_case.execute(request_)
        path = assessments_path
        data = json.loads(path.read_text())
        assert all("student_id" in entry for entry in data)

    def test_output_contains_submission_id(self, use_case, request_, assessments_path):
        use_case.execute(request_)
        path = assessments_path
        data = json.loads(path.read_text())
        assert all("submission_id" in entry for entry in data)

    def test_output_contains_criteria(self, use_case, request_, assessments_path):
        use_case.execute(request_)
        path = assessments_path
        data = json.loads(path.read_text())
        assert all("criteria" in entry for entry in data)

    def test_correct_number_of_assessments_written(self, use_case, request_, assessments_path):
        use_case.execute(request_)
        path = assessments_path
        data = json.loads(path.read_text())
        assert len(data) == len(RUBRIC_ASSESSMENTS)

    def test_fetched_with_correct_ids(self, use_case, request_, client):
        use_case.execute(request_)
        assert (COURSE_ID, ASSIGNMENT_ID) in client.fetch_rubric_calls

    def test_result_message_contains_course_id(self, use_case, request_):
        result = use_case.execute(request_)
        assert str(COURSE_ID) in result.message

    def test_result_message_contains_assignment_id(self, use_case, request_):
        result = use_case.execute(request_)
        assert str(ASSIGNMENT_ID) in result.message

    def test_result_saved_path_matches_output_file(self, use_case, request_, assessments_path):
        result = use_case.execute(request_)
        expected = assessments_path
        assert result.saved_path == expected


# ---------------------------------------------------------------------------
# Rubric definition
# ---------------------------------------------------------------------------


class TestRubricDefinitionHappyPath:
    def test_definition_file_is_created(self, use_case, request_, definition_path):
        use_case.execute(request_)
        expected = definition_path
        assert expected.exists()

    def test_definition_fetched_with_correct_ids(self, use_case, request_, client):
        use_case.execute(request_)
        assert (COURSE_ID, ASSIGNMENT_ID) in client.fetch_rubric_definition_calls

    def test_definition_json_matches_schema_required_fields(
        self, use_case, request_, definition_path
    ):
        use_case.execute(request_)
        path = definition_path
        data = json.loads(path.read_text())
        for field in (
            "rubric_id",
            "title",
            "points_possible",
            "free_form_criterion_comments",
            "criteria",
        ):
            assert field in data
        for criterion in data["criteria"]:
            for field in ("id", "description", "long_description", "points", "ratings"):
                assert field in criterion
            for rating in criterion["ratings"]:
                for field in ("id", "description", "long_description", "points"):
                    assert field in rating

    def test_result_includes_definition_saved_path(self, use_case, request_, definition_path):
        result = use_case.execute(request_)
        expected = definition_path
        assert result.definition_saved_path == expected


class TestNoAssociatedRubric:
    def test_no_definition_file_when_assignment_has_no_rubric(
        self, use_case, request_, client, definition_path
    ):
        client.rubric_definition = None
        use_case.execute(request_)
        assert not definition_path.exists()

    def test_result_definition_saved_path_is_none(self, use_case, request_, client):
        client.rubric_definition = None
        result = use_case.execute(request_)
        assert result.definition_saved_path is None

    def test_assessment_file_still_written(
        self, use_case, request_, client, tmp_path, assessments_path
    ):
        client.rubric_definition = None
        use_case.execute(request_)
        assert assessments_path.exists()


class TestRubricDefinitionApiErrors:
    def test_timeout_on_definition_fetch_propagates(self, use_case, request_, client):
        client.fetch_rubric_definition_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError, match="network timeout"):
            use_case.execute(request_)

    def test_unauthorized_on_definition_fetch_propagates(self, use_case, request_, client):
        client.fetch_rubric_definition_error = PermissionError("401 Unauthorized")
        with pytest.raises(PermissionError, match="401"):
            use_case.execute(request_)


# ---------------------------------------------------------------------------
# Empty assessments
# ---------------------------------------------------------------------------


class TestEmptyAssessments:
    def test_output_is_empty_list_when_no_assessments(
        self, use_case, request_, client, tmp_path, assessments_path
    ):
        client.rubric_assessments = []
        use_case.execute(request_)
        path = assessments_path
        assert json.loads(path.read_text()) == []

    def test_output_file_still_created_when_no_assessments(
        self, use_case, request_, client, assessments_path
    ):
        client.rubric_assessments = []
        use_case.execute(request_)
        assert assessments_path.exists()


# ---------------------------------------------------------------------------
# API errors
# ---------------------------------------------------------------------------


class TestApiErrors:
    def test_timeout_propagates(self, use_case, request_, client):
        client.fetch_rubric_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError, match="network timeout"):
            use_case.execute(request_)

    def test_unauthorized_propagates(self, use_case, request_, client):
        client.fetch_rubric_error = PermissionError("401 Unauthorized")
        with pytest.raises(PermissionError, match="401"):
            use_case.execute(request_)

    def test_no_file_written_on_error(self, use_case, request_, client, tmp_path):
        client.fetch_rubric_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError):
            use_case.execute(request_)
        assert not any(tmp_path.rglob("*.json"))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_raises_for_zero_course_id(self, use_case, folder):
        with pytest.raises(ValueError, match="course_id must be greater than zero"):
            use_case.execute(
                DownloadRubricAssessmentRequest(
                    course_id=0,
                    assignment=ASSIGNMENT,
                    folder=folder,
                )
            )

    def test_raises_for_negative_course_id(self, use_case, folder):
        with pytest.raises(ValueError, match="course_id must be greater than zero"):
            use_case.execute(
                DownloadRubricAssessmentRequest(
                    course_id=-1,
                    assignment=ASSIGNMENT,
                    folder=folder,
                )
            )

    def test_raises_for_zero_assignment_id(self, use_case, folder):
        with pytest.raises(ValueError, match="assignment_id must be greater than zero"):
            use_case.execute(
                DownloadRubricAssessmentRequest(
                    course_id=COURSE_ID,
                    assignment=CanvasAssignment(id=0, name=""),
                    folder=folder,
                )
            )

    def test_raises_for_negative_assignment_id(self, use_case, folder):
        with pytest.raises(ValueError, match="assignment_id must be greater than zero"):
            use_case.execute(
                DownloadRubricAssessmentRequest(
                    course_id=COURSE_ID,
                    assignment=CanvasAssignment(id=-1, name=""),
                    folder=folder,
                )
            )

    def test_client_not_called_for_invalid_request(self, use_case, folder, client):
        with pytest.raises(ValueError):
            use_case.execute(
                DownloadRubricAssessmentRequest(
                    course_id=0,
                    assignment=ASSIGNMENT,
                    folder=folder,
                )
            )
        assert client.fetch_rubric_calls == []


# ---------------------------------------------------------------------------
# Workspace layout
# ---------------------------------------------------------------------------


class TestWorkspaceLayout:
    def test_folder_is_tagged_with_the_module_from_the_name(self, use_case, request_, folder):
        result = use_case.execute(request_)
        assert result.assignment_folder.name == f"{ASSIGNMENT_ID}_m4"
        assert result.saved_path.parent == result.assignment_folder.path

    def test_unnamed_assignment_gets_an_untagged_folder(self, use_case, folder):
        result = use_case.execute(
            DownloadRubricAssessmentRequest(
                course_id=COURSE_ID,
                assignment=CanvasAssignment(id=ASSIGNMENT_ID, name=""),
                folder=folder,
            )
        )
        assert result.assignment_folder.name == str(ASSIGNMENT_ID)

    def test_existing_folder_for_the_id_is_reused(self, use_case, folder):
        folder.original.assignment(ASSIGNMENT_ID, 9).path.mkdir(parents=True)
        result = use_case.execute(
            DownloadRubricAssessmentRequest(
                course_id=COURSE_ID,
                assignment=CanvasAssignment(id=ASSIGNMENT_ID, name=""),
                folder=folder,
            )
        )
        assert result.assignment_folder.name == f"{ASSIGNMENT_ID}_m9"

    def test_manifest_records_both_files_and_the_assignment(self, use_case, request_, folder):
        use_case.execute(request_)
        manifest = load_manifest(folder.manifest_path)
        paths = {a.path: a for a in manifest.artifacts}
        assert set(paths) == {
            f"original/assignments/{ASSIGNMENT_ID}_m4/rubric_assessments.json",
            f"original/assignments/{ASSIGNMENT_ID}_m4/rubric_definition.json",
        }
        assert all(a.source_id == ASSIGNMENT_ID for a in paths.values())
        entry = manifest.assignment(ASSIGNMENT_ID)
        assert entry is not None
        assert entry.name == ASSIGNMENT.name
        assert entry.module_number == 4
        assert entry.has_rubric is True
        assert manifest.canvas_course_id == COURSE_ID

    def test_assignment_without_rubric_is_recorded_as_such(
        self, use_case, request_, client, folder
    ):
        client.rubric_definition = None
        use_case.execute(request_)
        manifest = load_manifest(folder.manifest_path)
        assert manifest.assignment(ASSIGNMENT_ID).has_rubric is False
        assert manifest.artifacts_of_kind("rubric_definition") == ()

    def test_second_download_is_refused(self, use_case, request_, client):
        use_case.execute(request_)
        with pytest.raises(ArtifactExistsError, match="already downloaded"):
            use_case.execute(request_)
        assert len(client.fetch_rubric_calls) == 1
