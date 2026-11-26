from __future__ import annotations

import json
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
from GAVEL.app.usecases.download_assignment_submissions import (
    DownloadAssignmentSubmissionsRequest,
    DownloadAssignmentSubmissionsUseCase,
    build_submission_filename,
)
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import load_manifest
from GAVEL.app.workspace.recording import ArtifactExistsError

# ---------------------------------------------------------------------------
# build_submission_filename
# ---------------------------------------------------------------------------


class TestBuildSubmissionFilename:
    def test_plain_name(self):
        assert build_submission_filename("Alvarez, Jordan", 123, 456, "essay.pdf") == (
            "AlvarezJordan_123_456_essay.pdf"
        )

    def test_name_with_spaces(self):
        assert build_submission_filename("Racowsky, Mary Jane", 1, 2, "a.pdf") == (
            "RacowskyMaryJane_1_2_a.pdf"
        )

    def test_name_with_hyphen(self):
        assert build_submission_filename("Tabuchi-Lee, Pat", 1, 2, "a.pdf") == (
            "Tabuchi-LeePat_1_2_a.pdf"
        )

    def test_name_with_apostrophe(self):
        assert build_submission_filename("O'Brien, Pat", 1, 2, "a.pdf") == "O'BrienPat_1_2_a.pdf"

    def test_two_students_with_the_same_display_name_get_different_filenames(self):
        first = build_submission_filename("Nguyen, Pat", 1, 100, "a.pdf")
        second = build_submission_filename("Nguyen, Pat", 2, 101, "a.pdf")
        assert first != second


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------

COURSE_ID = 253450
ASSIGNMENT_ID = 7178356
ASSIGNMENT = CanvasAssignment(
    id=ASSIGNMENT_ID, name="ADJ 1: Assignment", submission_types=("online_upload",)
)


class MockCanvasClient(CanvasClient):
    def __init__(self) -> None:
        self.submissions: list[CanvasSubmission] = []
        self.bytes_by_url: dict[str, bytes] = {}
        self.error_by_url: dict[str, Exception] = {}
        self.list_submissions_calls: list[tuple[int, int]] = []
        self.fetch_attachment_calls: list[str] = []

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
        raise NotImplementedError

    def fetch_rubric_definition(
        self, course_id: int, assignment_id: int
    ) -> RubricDefinition | None:
        raise NotImplementedError

    def list_assignment_submissions(
        self, course_id: int, assignment_id: int
    ) -> list[CanvasSubmission]:
        self.list_submissions_calls.append((course_id, assignment_id))
        return self.submissions

    def fetch_attachment_bytes(self, url: str) -> bytes:
        self.fetch_attachment_calls.append(url)
        if url in self.error_by_url:
            raise self.error_by_url[url]
        return self.bytes_by_url[url]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> MockCanvasClient:
    return MockCanvasClient()


@pytest.fixture
def use_case(client: MockCanvasClient) -> DownloadAssignmentSubmissionsUseCase:
    return DownloadAssignmentSubmissionsUseCase(canvas_client=client)


@pytest.fixture
def folder(tmp_path: Path) -> CourseFolder:
    return Workspace(tmp_path).course(CourseKey.parse("ser222_25sc_12345"))


@pytest.fixture
def request_(folder: CourseFolder) -> DownloadAssignmentSubmissionsRequest:
    return DownloadAssignmentSubmissionsRequest(
        course_id=COURSE_ID, assignment=ASSIGNMENT, folder=folder
    )


def _submission(
    user_id: int, sortable_name: str, late: bool = False, attachments: tuple = ()
) -> CanvasSubmission:
    return CanvasSubmission(
        user_id=user_id, sortable_name=sortable_name, late=late, attachments=attachments
    )


def _attachment(id_: int, display_name: str) -> CanvasAttachment:
    return CanvasAttachment(id=id_, display_name=display_name, url=f"https://canvas.example/{id_}")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_zip_file_is_created(self, use_case, request_, client):
        attachment = _attachment(1, "essay.pdf")
        client.submissions = [_submission(100, "Alvarez, Jordan", attachments=(attachment,))]
        client.bytes_by_url[attachment.url] = b"hello"

        result = use_case.execute(request_)

        assert result.saved_path.exists()
        assert result.attachments_saved == 1

    def test_zip_contains_the_expected_entry_and_bytes(self, use_case, request_, client):
        attachment = _attachment(1, "essay.pdf")
        client.submissions = [_submission(100, "Alvarez, Jordan", attachments=(attachment,))]
        client.bytes_by_url[attachment.url] = b"hello"

        result = use_case.execute(request_)

        with zipfile.ZipFile(result.saved_path) as archive:
            names = archive.namelist()
            assert names == ["AlvarezJordan_100_1_essay.pdf"]
            assert archive.read(names[0]) == b"hello"

    def test_zip_is_extracted_next_to_itself(self, use_case, request_, client):
        attachment = _attachment(1, "essay.pdf")
        client.submissions = [_submission(100, "Alvarez, Jordan", attachments=(attachment,))]
        client.bytes_by_url[attachment.url] = b"hello"

        result = use_case.execute(request_)

        extracted = result.assignment_folder.submissions_extracted_dir
        assert (extracted / "AlvarezJordan_100_1_essay.pdf").read_bytes() == b"hello"

    def test_sidecar_json_lists_the_attachment(self, use_case, request_, client):
        attachment = _attachment(1, "essay.pdf")
        client.submissions = [
            _submission(100, "Alvarez, Jordan", late=True, attachments=(attachment,))
        ]
        client.bytes_by_url[attachment.url] = b"hello"

        use_case.execute(request_)

        data = json.loads(
            request_.folder.original.assignment(ASSIGNMENT_ID).submissions_json.read_text()
        )
        assert len(data) == 1
        assert data[0]["user_id"] == 100
        assert data[0]["attachment_id"] == 1
        assert data[0]["late"] is True
        assert data[0]["saved_as"] == "AlvarezJordan_100_1_essay.pdf"

    def test_several_attachments_for_one_student_are_all_saved(self, use_case, request_, client):
        a1, a2 = _attachment(1, "a.pdf"), _attachment(2, "b.pdf")
        client.submissions = [_submission(100, "Alvarez, Jordan", attachments=(a1, a2))]
        client.bytes_by_url[a1.url] = b"one"
        client.bytes_by_url[a2.url] = b"two"

        result = use_case.execute(request_)

        assert result.attachments_saved == 2
        with zipfile.ZipFile(result.saved_path) as archive:
            assert len(archive.namelist()) == 2

    def test_result_message_contains_course_and_assignment_id(self, use_case, request_, client):
        result = use_case.execute(request_)
        assert str(COURSE_ID) in result.message
        assert str(ASSIGNMENT_ID) in result.message

    def test_fetched_with_correct_ids(self, use_case, request_, client):
        use_case.execute(request_)
        assert (COURSE_ID, ASSIGNMENT_ID) in client.list_submissions_calls


# ---------------------------------------------------------------------------
# Students with no attachments
# ---------------------------------------------------------------------------


class TestNoAttachments:
    def test_student_with_no_attachments_is_skipped_and_counted(self, use_case, request_, client):
        client.submissions = [_submission(100, "Alvarez, Jordan", attachments=())]

        result = use_case.execute(request_)

        assert result.attachments_saved == 0
        assert result.students_with_no_attachments == 1
        with zipfile.ZipFile(result.saved_path) as archive:
            assert archive.namelist() == []

    def test_no_attachments_is_noted_in_the_message(self, use_case, request_, client):
        client.submissions = [_submission(100, "Alvarez, Jordan", attachments=())]
        result = use_case.execute(request_)
        assert "1 student" in result.message

    def test_empty_submission_list_still_writes_an_empty_zip(self, use_case, request_, client):
        result = use_case.execute(request_)
        assert result.saved_path.exists()
        assert result.attachments_saved == 0


# ---------------------------------------------------------------------------
# A failed attachment
# ---------------------------------------------------------------------------


class TestFailedAttachment:
    def test_one_failed_attachment_does_not_block_the_others(self, use_case, request_, client):
        ok, bad = _attachment(1, "a.pdf"), _attachment(2, "b.pdf")
        client.submissions = [
            _submission(100, "Alvarez, Jordan", attachments=(ok,)),
            _submission(200, "Kim, Riley", attachments=(bad,)),
        ]
        client.bytes_by_url[ok.url] = b"fine"
        client.error_by_url[bad.url] = TimeoutError("network timeout")

        result = use_case.execute(request_)

        assert result.attachments_saved == 1
        assert len(result.failed_attachments) == 1
        assert result.failed_attachments[0].user_id == 200
        with zipfile.ZipFile(result.saved_path) as archive:
            assert archive.namelist() == ["AlvarezJordan_100_1_a.pdf"]

    def test_failure_is_reported_in_the_message(self, use_case, request_, client):
        bad = _attachment(2, "b.pdf")
        client.submissions = [_submission(200, "Kim, Riley", attachments=(bad,))]
        client.error_by_url[bad.url] = TimeoutError("network timeout")

        result = use_case.execute(request_)

        assert "1 attachment" in result.message
        assert "failed" in result.message


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_raises_for_zero_course_id(self, use_case, folder):
        with pytest.raises(ValueError, match="course_id must be greater than zero"):
            use_case.execute(
                DownloadAssignmentSubmissionsRequest(
                    course_id=0, assignment=ASSIGNMENT, folder=folder
                )
            )

    def test_raises_for_zero_assignment_id(self, use_case, folder):
        with pytest.raises(ValueError, match="assignment_id must be greater than zero"):
            use_case.execute(
                DownloadAssignmentSubmissionsRequest(
                    course_id=COURSE_ID, assignment=CanvasAssignment(id=0, name=""), folder=folder
                )
            )

    def test_client_not_called_for_invalid_request(self, use_case, folder, client):
        with pytest.raises(ValueError):
            use_case.execute(
                DownloadAssignmentSubmissionsRequest(
                    course_id=0, assignment=ASSIGNMENT, folder=folder
                )
            )
        assert client.list_submissions_calls == []


# ---------------------------------------------------------------------------
# Workspace layout and manifest
# ---------------------------------------------------------------------------


class TestWorkspaceLayout:
    def test_manifest_records_the_submissions_artifact(self, use_case, request_, folder, client):
        attachment = _attachment(1, "essay.pdf")
        client.submissions = [_submission(100, "Alvarez, Jordan", attachments=(attachment,))]
        client.bytes_by_url[attachment.url] = b"hello"

        use_case.execute(request_)

        manifest = load_manifest(folder.manifest_path)
        entries = manifest.artifacts_of_kind("assignment_submissions")
        assert len(entries) == 1
        assert entries[0].source_id == ASSIGNMENT_ID
        assert entries[0].label == ASSIGNMENT.name

    def test_manifest_records_the_assignment(self, use_case, request_, folder):
        use_case.execute(request_)
        entry = load_manifest(folder.manifest_path).assignment(ASSIGNMENT_ID)
        assert entry is not None
        assert entry.submission_types == ("online_upload",)

    def test_second_download_is_refused(self, use_case, request_, client):
        use_case.execute(request_)
        with pytest.raises(ArtifactExistsError, match="already downloaded"):
            use_case.execute(request_)
        assert len(client.list_submissions_calls) == 1

    def test_overwrite_replaces_the_zip(self, use_case, request_, client, folder):
        attachment = _attachment(1, "essay.pdf")
        client.submissions = [_submission(100, "Alvarez, Jordan", attachments=(attachment,))]
        client.bytes_by_url[attachment.url] = b"hello"
        use_case.execute(request_)

        client.submissions = []
        use_case.execute(
            DownloadAssignmentSubmissionsRequest(
                course_id=COURSE_ID, assignment=ASSIGNMENT, folder=folder, overwrite=True
            )
        )

        with zipfile.ZipFile(
            request_.folder.original.assignment(ASSIGNMENT_ID).submissions_zip
        ) as archive:
            assert archive.namelist() == []
