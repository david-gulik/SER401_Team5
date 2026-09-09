"""
Unit tests for DownloadAllRubricAssessmentsUseCase using a mock CanvasClient.

Regression coverage for SCRUM-223: "Download All" previously downloaded a
rubric assessment for at most one hard-coded assignment regardless of how
many assignments the course actually had. This use case is what the
Download All workflow now delegates to for rubric assessments, so an
N-assignment course must always produce N distinct output files.

Also covers SCRUM-221's follow-up: the batch use case categorizes each
outcome as succeeded / skipped / failed, where "skipped" means the
assignment genuinely has no rubric attached (via
DownloadRubricAssessmentResult.definition_saved_path, backed by
fetch_rubric_definition from SCRUM-222) — not just an empty assessment
list. An assignment with a rubric that nobody has graded yet still counts
as succeeded.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasCourseData
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.rubric_assessment import RubricAssessment, RubricCriterionScore
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.download_all_rubric_assessments import (
    DownloadAllRubricAssessmentsRequest,
    DownloadAllRubricAssessmentsUseCase,
)

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

COURSE_ID = 253450

ASSIGNMENTS = [
    CanvasAssignment(id=101, name="Homework 1"),
    CanvasAssignment(id=102, name="Homework 2"),
    CanvasAssignment(id=103, name="Homework 3"),
]

RUBRIC_ASSESSMENTS = [
    RubricAssessment(
        student_id=100001,
        submission_id=9001,
        criteria=(RubricCriterionScore(criterion_id="crit_1", points=4.0, comments=""),),
    ),
]

RUBRIC_DEFINITION = RubricDefinition(
    rubric_id="rub_1",
    title="Homework Rubric",
    points_possible=4.0,
    free_form_criterion_comments=False,
    criteria=(),
)


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------


class MockCanvasClient(CanvasClient):
    def __init__(self) -> None:
        self.assignments: list[CanvasAssignment] = ASSIGNMENTS
        self.rubric_assessments: list[RubricAssessment] = RUBRIC_ASSESSMENTS
        # Per-assignment overrides, e.g. {102: []} or {102: None}.
        self.rubric_assessments_for: dict[int, list[RubricAssessment]] = {}
        # Default: every assignment has a rubric attached.
        self.rubric_definition: RubricDefinition | None = RUBRIC_DEFINITION
        self.rubric_definition_for: dict[int, RubricDefinition | None] = {}
        self.fetch_rubric_error_for: set[int] = set()
        self.list_assignments_error: Exception | None = None
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

    def list_assignments(self, course_id: int) -> list[CanvasAssignment]:
        if self.list_assignments_error:
            raise self.list_assignments_error
        return self.assignments

    def fetch_rubric_assessments(
        self, course_id: int, assignment_id: int
    ) -> list[RubricAssessment]:
        self.fetch_rubric_calls.append((course_id, assignment_id))
        if assignment_id in self.fetch_rubric_error_for:
            raise RuntimeError(f"Canvas error for assignment {assignment_id}")
        return self.rubric_assessments_for.get(assignment_id, self.rubric_assessments)

    def fetch_rubric_definition(
        self, course_id: int, assignment_id: int
    ) -> RubricDefinition | None:
        self.fetch_rubric_definition_calls.append((course_id, assignment_id))
        if assignment_id in self.rubric_definition_for:
            return self.rubric_definition_for[assignment_id]
        return self.rubric_definition


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> MockCanvasClient:
    return MockCanvasClient()


@pytest.fixture
def use_case(client: MockCanvasClient) -> DownloadAllRubricAssessmentsUseCase:
    return DownloadAllRubricAssessmentsUseCase(canvas_client=client)


@pytest.fixture
def request_(tmp_path: Path) -> DownloadAllRubricAssessmentsRequest:
    return DownloadAllRubricAssessmentsRequest(course_id=COURSE_ID, output_dir=tmp_path)


# ---------------------------------------------------------------------------
# Happy path: N assignments -> N distinct outputs
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_one_outcome_per_assignment(self, use_case, request_):
        result = use_case.execute(request_)
        assert len(result.outcomes) == len(ASSIGNMENTS)

    def test_all_assignments_fetched(self, use_case, request_, client):
        use_case.execute(request_)
        fetched_ids = [aid for _, aid in client.fetch_rubric_calls]
        assert fetched_ids == [a.id for a in ASSIGNMENTS]

    def test_writes_one_distinct_file_per_assignment(self, use_case, request_, tmp_path):
        result = use_case.execute(request_)
        saved_paths = [o.saved_path for o in result.succeeded]

        assert len(saved_paths) == len(ASSIGNMENTS)
        assert len(set(saved_paths)) == len(ASSIGNMENTS), "output paths must be distinct"
        for path in saved_paths:
            assert path.exists()

    def test_filenames_include_assignment_identifier(self, use_case, request_):
        result = use_case.execute(request_)
        for assignment, outcome in zip(ASSIGNMENTS, result.succeeded, strict=True):
            assert str(assignment.id) in outcome.saved_path.name

    def test_all_outcomes_succeeded(self, use_case, request_):
        result = use_case.execute(request_)
        assert len(result.succeeded) == len(ASSIGNMENTS)
        assert result.skipped == ()
        assert result.failed == ()

    def test_outcome_content_matches_assessments(self, use_case, request_):
        result = use_case.execute(request_)
        for outcome in result.succeeded:
            data = json.loads(outcome.saved_path.read_text())
            assert len(data) == len(RUBRIC_ASSESSMENTS)

    def test_outcome_assessment_count_matches(self, use_case, request_):
        result = use_case.execute(request_)
        for outcome in result.succeeded:
            assert outcome.assessment_count == len(RUBRIC_ASSESSMENTS)

    def test_outcome_has_rubric_true(self, use_case, request_):
        result = use_case.execute(request_)
        for outcome in result.succeeded:
            assert outcome.has_rubric is True


# ---------------------------------------------------------------------------
# Skipped: no rubric attached to the assignment
# ---------------------------------------------------------------------------


class TestSkipped:
    def test_no_rubric_is_skipped_not_succeeded(self, use_case, request_, client):
        client.rubric_definition_for = {102: None}
        result = use_case.execute(request_)

        assert len(result.succeeded) == 2
        assert len(result.skipped) == 1
        assert result.skipped[0].assignment_id == 102

    def test_skipped_outcome_still_has_saved_path(self, use_case, request_, client):
        client.rubric_definition_for = {102: None}
        result = use_case.execute(request_)
        skipped = result.skipped[0]
        assert skipped.saved_path is not None
        assert skipped.saved_path.exists()
        assert skipped.error is None

    def test_skipped_outcome_has_rubric_false(self, use_case, request_, client):
        client.rubric_definition_for = {102: None}
        result = use_case.execute(request_)
        assert result.skipped[0].has_rubric is False

    def test_status_property_reports_skipped(self, use_case, request_, client):
        client.rubric_definition_for = {102: None}
        result = use_case.execute(request_)
        outcome = next(o for o in result.outcomes if o.assignment_id == 102)
        assert outcome.status == "skipped"

    def test_all_no_rubric_produces_all_skipped(self, use_case, request_, client):
        client.rubric_definition = None
        result = use_case.execute(request_)
        assert len(result.skipped) == len(ASSIGNMENTS)
        assert result.succeeded == ()
        assert result.failed == ()

    def test_rubric_present_but_ungraded_is_succeeded_not_skipped(self, use_case, request_, client):
        """The fix this covers: a rubric-bearing assignment with zero
        assessments (nobody graded yet) must NOT be treated the same as
        an assignment with no rubric at all."""
        client.rubric_assessments_for = {102: []}
        result = use_case.execute(request_)

        outcome = next(o for o in result.outcomes if o.assignment_id == 102)
        assert outcome.status == "succeeded"
        assert outcome.has_rubric is True
        assert outcome.assessment_count == 0
        assert result.skipped == ()


# ---------------------------------------------------------------------------
# Per-assignment failure isolation
# ---------------------------------------------------------------------------


class TestPartialFailure:
    def test_one_failing_assignment_does_not_block_others(self, use_case, request_, client):
        client.fetch_rubric_error_for = {102}
        result = use_case.execute(request_)

        assert len(result.succeeded) == 2
        assert len(result.failed) == 1
        assert result.failed[0].assignment_id == 102

    def test_all_assignments_still_attempted_after_failure(self, use_case, request_, client):
        client.fetch_rubric_error_for = {101}
        use_case.execute(request_)
        fetched_ids = [aid for _, aid in client.fetch_rubric_calls]
        assert fetched_ids == [a.id for a in ASSIGNMENTS]

    def test_failure_outcome_has_no_saved_path(self, use_case, request_, client):
        client.fetch_rubric_error_for = {103}
        result = use_case.execute(request_)
        failing = next(o for o in result.outcomes if o.assignment_id == 103)
        assert failing.saved_path is None
        assert failing.assessment_count is None
        assert failing.has_rubric is None
        assert failing.error is not None
        assert failing.status == "failed"

    def test_successful_outcomes_still_written_when_another_fails(self, use_case, request_, client):
        client.fetch_rubric_error_for = {101}
        result = use_case.execute(request_)
        for outcome in result.succeeded:
            assert outcome.saved_path.exists()


# ---------------------------------------------------------------------------
# No assignments / list_assignments errors
# ---------------------------------------------------------------------------


class TestNoAssignments:
    def test_empty_course_produces_no_outcomes(self, use_case, request_, client):
        client.assignments = []
        result = use_case.execute(request_)
        assert result.outcomes == ()

    def test_list_assignments_error_propagates(self, use_case, request_, client):
        client.list_assignments_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError, match="network timeout"):
            use_case.execute(request_)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_raises_for_zero_course_id(self, use_case, tmp_path):
        with pytest.raises(ValueError, match="course_id must be greater than zero"):
            use_case.execute(DownloadAllRubricAssessmentsRequest(course_id=0, output_dir=tmp_path))

    def test_raises_for_negative_course_id(self, use_case, tmp_path):
        with pytest.raises(ValueError, match="course_id must be greater than zero"):
            use_case.execute(DownloadAllRubricAssessmentsRequest(course_id=-1, output_dir=tmp_path))

    def test_client_not_called_for_invalid_request(self, use_case, tmp_path, client):
        with pytest.raises(ValueError):
            use_case.execute(DownloadAllRubricAssessmentsRequest(course_id=0, output_dir=tmp_path))
        assert client.fetch_rubric_calls == []
