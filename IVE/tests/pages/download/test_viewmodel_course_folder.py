"""Course folder naming in DownloadViewModel: derived from selections, or typed by hand."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.core.status import Status
from GAVEL.pages.download.viewmodel import (
    GRADEBOOK_DOWNLOAD,
    DownloadViewModel,
    FocusCourseFolder,
    ShowError,
)
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

SIS_COURSE = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")
TRAINING = CanvasCourse(id=213877, name="IVE Capstone", course_code="TRN-2026Spring-IVECapstone")


class GradebookCanvasClient(FakeCanvasClient):
    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        self.download_calls.append("fetch_gradebook_csv")
        return b"Student,ID\n"


@pytest.fixture
def canvas() -> GradebookCanvasClient:
    return GradebookCanvasClient(courses=[SIS_COURSE, TRAINING])


@pytest.fixture
def vm(qapp, canvas: GradebookCanvasClient, tmp_path: Path) -> DownloadViewModel:
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    vm.load_courses()
    return vm


def events(vm: DownloadViewModel) -> list:
    seen: list = []
    vm.event_raised.connect(seen.append)
    return seen


def test_training_course_cannot_be_named_automatically(vm, canvas):
    vm.set_course_id(str(TRAINING.id))
    state = vm.get_state()
    assert state.course_folder_name is None
    assert "no ASU course code" in state.course_folder_error
    assert "type a course folder name" in state.course_folder_error

    seen = events(vm)
    vm.download_gradebook()
    assert seen == [ShowError(state.course_folder_error), FocusCourseFolder()]
    assert canvas.download_calls == []


def test_typed_folder_name_unblocks_the_download(vm, canvas, tmp_path):
    vm.set_course_id(str(TRAINING.id))
    vm.set_manual_course_folder("ser401_26f_99999")
    state = vm.get_state()
    assert state.course_folder_name == "courses/ser401_26f_99999"
    assert state.course_folder_error is None

    vm.download_gradebook()
    state = vm.get_state()
    assert state.status is Status.NOMINAL
    expected = tmp_path / "courses" / "ser401_26f_99999" / "original" / "gradebook.csv"
    assert state.last_saved_path == str(expected)
    assert expected.exists()


def test_typed_folder_name_overrides_the_canvas_code(vm):
    vm.set_course_id(str(SIS_COURSE.id))
    assert vm.get_state().course_folder_name == "courses/ser402_26fc_87275"
    vm.set_manual_course_folder("SER402_26FC_00001")  # folder names are lower case; rejected
    assert vm.get_state().course_folder_name is None
    vm.set_manual_course_folder("ser402_26fc_00001")
    assert vm.get_state().course_folder_name == "courses/ser402_26fc_00001"


def test_clearing_the_typed_name_goes_back_to_the_selections(vm):
    vm.set_course_id(str(SIS_COURSE.id))
    vm.set_manual_course_folder("ser401_26f_99999")
    vm.set_manual_course_folder("")
    assert vm.get_state().course_folder_name == "courses/ser402_26fc_87275"


def test_malformed_typed_name_is_explained_and_blocks(vm, canvas):
    vm.set_course_id(str(SIS_COURSE.id))
    vm.set_manual_course_folder("my course")
    state = vm.get_state()
    assert state.course_folder_name is None
    assert "ser222_25sc_12345" in state.course_folder_error

    seen = events(vm)
    vm.download_gradebook()
    assert seen == [ShowError(state.course_folder_error), FocusCourseFolder()]
    assert canvas.download_calls == []


def test_changing_the_typed_name_forgets_completed_downloads(vm):
    vm.set_course_id(str(SIS_COURSE.id))
    vm.download_gradebook()
    assert GRADEBOOK_DOWNLOAD in vm.get_state().completed
    vm.set_manual_course_folder("ser402_26fc_00001")
    assert vm.get_state().completed == frozenset()


def test_whitespace_only_is_treated_as_empty(vm):
    vm.set_course_id(str(SIS_COURSE.id))
    vm.set_manual_course_folder("   ")
    assert vm.get_state().manual_course_folder == ""
    assert vm.get_state().course_folder_name == "courses/ser402_26fc_87275"
