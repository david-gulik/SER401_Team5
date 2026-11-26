"""Assignment submissions resolution in DownloadViewModel with one download per listed assignment."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import (
    CanvasAssignment,
    CanvasAttachment,
    CanvasCourse,
    CanvasSubmission,
)
from GAVEL.core.status import Status
from GAVEL.pages.download.viewmodel import DownloadViewModel, ShowError, ShowInfo
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_viewmodel_roster import wait_for_workers

COURSE_ID = "213877"
COURSE = CanvasCourse(id=213877, name="SER 401", course_code="2026FallC-X-SER401-12345")
ASSIGNMENTS = [
    CanvasAssignment(id=7, name="ADJ 1", submission_types=("online_upload",)),
    CanvasAssignment(id=9, name="ADJ 2", submission_types=("online_upload",)),
]
NO_UPLOAD = CanvasAssignment(id=12, name="Gradescope HW", submission_types=("external_tool",))


def _submission() -> CanvasSubmission:
    attachment = CanvasAttachment(id=1, display_name="essay.pdf", url="https://canvas.example/1")
    return CanvasSubmission(
        user_id=100, sortable_name="Crain, Lindy", late=False, attachments=(attachment,)
    )


class SubmissionsCanvasClient(FakeCanvasClient):
    """Serves one submission per assignment and records which were fetched.
    Any assignment id in ``failing`` raises an error so that partial failures can
    be exercised.
    """

    def __init__(
        self,
        failing: set[int] = frozenset(),
        assignments: list[CanvasAssignment] = ASSIGNMENTS,
    ) -> None:
        super().__init__(courses=[COURSE], assignments=assignments)
        self.failing = set(failing)
        self.submissions_calls: list[int] = []

    def list_assignment_submissions(
        self, course_id: int, assignment_id: int
    ) -> list[CanvasSubmission]:
        self.submissions_calls.append(assignment_id)
        if assignment_id in self.failing:
            raise RuntimeError(f"no submissions for {assignment_id}")
        return [_submission()]

    def fetch_attachment_bytes(self, url: str) -> bytes:
        return b"hello"


@pytest.fixture
def canvas() -> SubmissionsCanvasClient:
    return SubmissionsCanvasClient()


def make_vm(qapp, canvas: FakeCanvasClient, tmp_path: Path) -> DownloadViewModel:
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    vm.load_courses()
    wait_for_workers(qapp)
    vm.set_course_id(COURSE_ID)
    return vm


def submissions_path(tmp_path: Path, assignment_id: int) -> Path:
    return (
        tmp_path
        / "courses"
        / "ser401_26fc_12345"
        / "original"
        / "assignments"
        / str(assignment_id)
        / "submissions.zip"
    )


@pytest.fixture
def vm(qapp, canvas: SubmissionsCanvasClient, tmp_path: Path) -> DownloadViewModel:
    return make_vm(qapp, canvas, tmp_path)


def events(vm: DownloadViewModel) -> list:
    seen: list = []
    vm.event_raised.connect(seen.append)
    return seen


def test_submissions_download_requires_an_assignment_after_the_course(vm, canvas):
    seen = events(vm)
    vm.download_assignment_submissions()
    assert seen == [ShowError("Select or enter at least one assignment first.")]
    assert canvas.submissions_calls == []


def test_single_assignment_download_keeps_the_use_case_message(qapp, vm, canvas, tmp_path):
    vm.set_assignment_ids("7")
    seen = events(vm)
    vm.download_assignment_submissions()
    wait_for_workers(qapp)
    assert canvas.submissions_calls == [7]
    state = vm.get_state()
    assert state.status is Status.NOMINAL
    assert submissions_path(tmp_path, 7).exists()
    assert state.last_saved_path == str(submissions_path(tmp_path, 7))
    assert seen == [ShowInfo(state.message)]
    assert "assignment 7" in state.message


def test_multiple_assignments_download_one_file_each(qapp, vm, canvas, tmp_path):
    vm.set_assignment_ids("9, 7")
    seen = events(vm)
    vm.download_assignment_submissions()
    wait_for_workers(qapp)
    assert canvas.submissions_calls == [9, 7]
    assert submissions_path(tmp_path, 9).exists()
    assert submissions_path(tmp_path, 7).exists()
    state = vm.get_state()
    assert state.status is Status.NOMINAL
    assert state.last_saved_path == str(submissions_path(tmp_path, 7))
    assert seen == [ShowInfo(state.message)]


def test_one_failing_assignment_does_not_stop_the_others(qapp, tmp_path):
    canvas = SubmissionsCanvasClient(failing={9})
    vm = make_vm(qapp, canvas, tmp_path)
    vm.set_assignment_ids("9, 7")
    seen = events(vm)
    vm.download_assignment_submissions()
    wait_for_workers(qapp)
    assert canvas.submissions_calls == [9, 7]
    state = vm.get_state()
    assert state.status is Status.WARNING
    assert "9: no submissions for 9" in state.message
    assert state.last_saved_path == str(submissions_path(tmp_path, 7))
    assert seen == [ShowError(state.message)]


def test_every_assignment_failing_is_critical(qapp, tmp_path):
    canvas = SubmissionsCanvasClient(failing={7, 9})
    vm = make_vm(qapp, canvas, tmp_path)
    vm.set_assignment_ids("7,9")
    seen = events(vm)
    vm.download_assignment_submissions()
    wait_for_workers(qapp)
    state = vm.get_state()
    assert state.status is Status.CRITICAL
    assert state.message == "7: no submissions for 7; 9: no submissions for 9"
    assert state.last_saved_path is None
    assert seen == [ShowError(state.message)]


def test_loaded_assignment_without_file_uploads_is_skipped_not_fetched(qapp, tmp_path):
    canvas = SubmissionsCanvasClient(assignments=[*ASSIGNMENTS, NO_UPLOAD])
    vm = make_vm(qapp, canvas, tmp_path)
    vm.load_assignments(COURSE_ID)
    wait_for_workers(qapp)
    vm.set_assignment_ids("12, 7")
    seen = events(vm)
    vm.download_assignment_submissions()
    wait_for_workers(qapp)
    assert canvas.submissions_calls == [7]
    state = vm.get_state()
    assert state.status is Status.WARNING
    assert "'Gradescope HW' does not accept file uploads" in state.message
    assert state.last_saved_path == str(submissions_path(tmp_path, 7))
    assert seen == [ShowInfo(state.message)]


def test_every_assignment_skipped_fetches_and_writes_nothing(qapp, tmp_path):
    canvas = SubmissionsCanvasClient(assignments=[NO_UPLOAD])
    vm = make_vm(qapp, canvas, tmp_path)
    vm.load_assignments(COURSE_ID)
    wait_for_workers(qapp)
    vm.set_assignment_ids("12")
    seen = events(vm)
    vm.download_assignment_submissions()
    wait_for_workers(qapp)
    assert canvas.submissions_calls == []
    state = vm.get_state()
    assert state.status is Status.WARNING
    assert "'Gradescope HW' does not accept file uploads" in state.message
    assert state.last_saved_path is None
    assert seen == [ShowInfo(state.message)]


def test_typed_id_that_was_never_loaded_is_still_attempted(qapp, tmp_path):
    canvas = SubmissionsCanvasClient(assignments=[NO_UPLOAD])
    vm = make_vm(qapp, canvas, tmp_path)
    vm.set_assignment_ids("12")  # never loaded, so submission_types is unknown here
    vm.download_assignment_submissions()
    wait_for_workers(qapp)
    assert canvas.submissions_calls == [12]
    assert vm.get_state().status is Status.NOMINAL
