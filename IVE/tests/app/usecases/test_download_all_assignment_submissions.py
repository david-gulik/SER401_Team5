"""
Unit tests for DownloadAllAssignmentSubmissionsUseCase using a mock CanvasClient.

Mirrors test_download_all_rubric_assessments.py: each assignment is attempted
independently, one failing does not stop the rest, and an assignment that
does not accept a direct file upload is reported as "skipped" rather than
"succeeded" - determined upfront from CanvasAssignment.submission_types, so a
skipped assignment is never fetched or written to disk at all.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import (
    CanvasAssignment,
    CanvasAttachment,
    CanvasCourseData,
    CanvasSubmission,
)
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.download_all_assignment_submissions import (
    DownloadAllAssignmentSubmissionsRequest,
    DownloadAllAssignmentSubmissionsUseCase,
)
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

COURSE_ID = 253450

ASSIGNMENTS = [
    CanvasAssignment(id=101, name="ADJ 1", submission_types=("online_upload",)),
    CanvasAssignment(id=102, name="ADJ 2", submission_types=("online_upload",)),
    CanvasAssignment(id=103, name="ADJ 3", submission_types=("online_upload",)),
]

ATTACHMENT = CanvasAttachment(id=1, display_name="essay.pdf", url="https://canvas.example/1")


def _submission() -> CanvasSubmission:
    return CanvasSubmission(
        user_id=1, sortable_name="Crain, Lindy", late=False, attachments=(ATTACHMENT,)
    )


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------


class MockCanvasClient(CanvasClient):
    def __init__(self) -> None:
        self.assignments: list[CanvasAssignment] = ASSIGNMENTS
        # Per-assignment submissions; default: one submission with one attachment.
        self.submissions_for: dict[int, list[CanvasSubmission]] = {}
        self.list_assignments_error: Exception | None = None
        self.list_submissions_error_for: set[int] = set()
        self.fetch_attachment_error: Exception | None = None
        self.list_submissions_calls: list[tuple[int, int]] = []

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
        raise NotImplementedError

    def fetch_rubric_definition(
        self, course_id: int, assignment_id: int
    ) -> RubricDefinition | None:
        raise NotImplementedError

    def list_assignment_submissions(
        self, course_id: int, assignment_id: int
    ) -> list[CanvasSubmission]:
        self.list_submissions_calls.append((course_id, assignment_id))
        if assignment_id in self.list_submissions_error_for:
            raise RuntimeError(f"Canvas error for assignment {assignment_id}")
        return self.submissions_for.get(assignment_id, [_submission()])

    def fetch_attachment_bytes(self, url: str) -> bytes:
        if self.fetch_attachment_error:
            raise self.fetch_attachment_error
        return b"hello"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> MockCanvasClient:
    return MockCanvasClient()


@pytest.fixture
def use_case(client: MockCanvasClient) -> DownloadAllAssignmentSubmissionsUseCase:
    return DownloadAllAssignmentSubmissionsUseCase(canvas_client=client)


@pytest.fixture
def folder(tmp_path: Path) -> CourseFolder:
    return Workspace(tmp_path).course(CourseKey.parse("ser222_25sc_12345"))


@pytest.fixture
def request_(folder: CourseFolder) -> DownloadAllAssignmentSubmissionsRequest:
    return DownloadAllAssignmentSubmissionsRequest(course_id=COURSE_ID, folder=folder)


# ---------------------------------------------------------------------------
# Happy path: N assignments -> N distinct outputs
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_one_outcome_per_assignment(self, use_case, request_):
        result = use_case.execute(request_)
        assert len(result.outcomes) == len(ASSIGNMENTS)

    def test_all_assignments_fetched(self, use_case, request_, client):
        use_case.execute(request_)
        fetched_ids = [aid for _, aid in client.list_submissions_calls]
        assert fetched_ids == [a.id for a in ASSIGNMENTS]

    def test_writes_one_distinct_file_per_assignment(self, use_case, request_):
        result = use_case.execute(request_)
        saved_paths = [o.saved_path for o in result.succeeded]

        assert len(saved_paths) == len(ASSIGNMENTS)
        assert len(set(saved_paths)) == len(ASSIGNMENTS), "output paths must be distinct"
        for path in saved_paths:
            assert path.exists()

    def test_all_outcomes_succeeded(self, use_case, request_):
        result = use_case.execute(request_)
        assert len(result.succeeded) == len(ASSIGNMENTS)
        assert result.skipped == ()
        assert result.failed == ()

    def test_outcome_attachments_saved_matches(self, use_case, request_):
        result = use_case.execute(request_)
        for outcome in result.succeeded:
            assert outcome.attachments_saved == 1

    def test_outcome_accepts_file_uploads_true(self, use_case, request_):
        result = use_case.execute(request_)
        for outcome in result.succeeded:
            assert outcome.accepts_file_uploads is True

    def test_zip_contains_the_attachment(self, use_case, request_):
        result = use_case.execute(request_)
        for outcome in result.succeeded:
            with zipfile.ZipFile(outcome.saved_path) as archive:
                assert len(archive.namelist()) == 1


# ---------------------------------------------------------------------------
# Skipped: assignment does not accept file uploads
# ---------------------------------------------------------------------------


class TestSkipped:
    def test_non_upload_assignment_is_skipped_not_succeeded(self, use_case, request_, client):
        client.assignments = [
            CanvasAssignment(id=101, name="ADJ 1", submission_types=("online_upload",)),
            CanvasAssignment(id=102, name="Gradescope HW", submission_types=("external_tool",)),
            CanvasAssignment(id=103, name="ADJ 3", submission_types=("online_upload",)),
        ]
        result = use_case.execute(request_)

        assert len(result.succeeded) == 2
        assert len(result.skipped) == 1
        assert result.skipped[0].assignment_id == 102

    def test_skipped_assignment_writes_no_file(self, use_case, request_, client, tmp_path):
        client.assignments = [
            CanvasAssignment(id=102, name="Gradescope HW", submission_types=("external_tool",))
        ]
        result = use_case.execute(request_)

        skipped = result.skipped[0]
        assert skipped.saved_path is None
        assert skipped.error is None
        assert not any(tmp_path.rglob("submissions.zip"))

    def test_skipped_assignment_is_never_fetched(self, use_case, request_, client):
        client.assignments = [
            CanvasAssignment(id=102, name="Gradescope HW", submission_types=("external_tool",))
        ]
        use_case.execute(request_)
        assert client.list_submissions_calls == []

    def test_assignment_with_no_submission_types_is_skipped(self, use_case, request_, client):
        client.assignments = [CanvasAssignment(id=102, name="No Types", submission_types=None)]
        result = use_case.execute(request_)
        assert result.skipped[0].assignment_id == 102

    def test_status_property_reports_skipped(self, use_case, request_, client):
        client.assignments = [
            CanvasAssignment(id=102, name="Gradescope HW", submission_types=("external_tool",))
        ]
        result = use_case.execute(request_)
        assert result.outcomes[0].status == "skipped"


# ---------------------------------------------------------------------------
# Per-assignment failure isolation
# ---------------------------------------------------------------------------


class TestPartialFailure:
    def test_one_failing_assignment_does_not_block_others(self, use_case, request_, client):
        client.list_submissions_error_for = {102}
        result = use_case.execute(request_)

        assert len(result.succeeded) == 2
        assert len(result.failed) == 1
        assert result.failed[0].assignment_id == 102

    def test_all_assignments_still_attempted_after_failure(self, use_case, request_, client):
        client.list_submissions_error_for = {101}
        use_case.execute(request_)
        fetched_ids = [aid for _, aid in client.list_submissions_calls]
        assert fetched_ids == [a.id for a in ASSIGNMENTS]

    def test_failure_outcome_has_no_saved_path(self, use_case, request_, client):
        client.list_submissions_error_for = {103}
        result = use_case.execute(request_)
        failing = next(o for o in result.outcomes if o.assignment_id == 103)
        assert failing.saved_path is None
        assert failing.attachments_saved is None
        assert failing.accepts_file_uploads is None
        assert failing.error is not None
        assert failing.status == "failed"


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
    def test_raises_for_zero_course_id(self, use_case, folder):
        with pytest.raises(ValueError, match="course_id must be greater than zero"):
            use_case.execute(DownloadAllAssignmentSubmissionsRequest(course_id=0, folder=folder))

    def test_client_not_called_for_invalid_request(self, use_case, folder, client):
        with pytest.raises(ValueError):
            use_case.execute(DownloadAllAssignmentSubmissionsRequest(course_id=0, folder=folder))
        assert client.list_submissions_calls == []


# ---------------------------------------------------------------------------
# Already downloaded
# ---------------------------------------------------------------------------


class TestAlreadyDownloaded:
    def test_second_run_leaves_files_alone_and_reports_them(self, use_case, request_, client):
        use_case.execute(request_)
        second = use_case.execute(request_)

        assert second.succeeded == ()
        assert second.failed == ()
        assert [o.assignment_id for o in second.already_downloaded] == [a.id for a in ASSIGNMENTS]
        assert all(o.status == "already_downloaded" for o in second.already_downloaded)

    def test_overwrite_downloads_again(self, use_case, request_, client, folder):
        use_case.execute(request_)
        result = use_case.execute(
            DownloadAllAssignmentSubmissionsRequest(
                course_id=COURSE_ID, folder=folder, overwrite=True
            )
        )
        assert len(result.succeeded) == len(ASSIGNMENTS)
        assert result.already_downloaded == ()

    def test_assignment_ids_limits_the_run_to_those_assignments(
        self, use_case, request_, client, folder
    ):
        use_case.execute(request_)
        client.list_submissions_calls.clear()

        result = use_case.execute(
            DownloadAllAssignmentSubmissionsRequest(
                course_id=COURSE_ID,
                folder=folder,
                overwrite=True,
                assignment_ids=frozenset({102}),
            )
        )

        assert [aid for _, aid in client.list_submissions_calls] == [102]
        assert [o.assignment_id for o in result.succeeded] == [102]


class TestProgress:
    def test_reports_once_up_front_and_once_per_assignment(self, use_case, request_):
        seen = []
        use_case.execute(request_, on_progress=seen.append)

        total = len(ASSIGNMENTS)
        assert [(p.done, p.total) for p in seen] == [(i, total) for i in range(total + 1)]
        assert [p.item for p in seen[1:]] == [a.name for a in ASSIGNMENTS]
