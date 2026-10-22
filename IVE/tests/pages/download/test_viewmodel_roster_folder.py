"""The roster download files itself under the roster class, not the selected Canvas course."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection, RosterRequest, TermInfo
from GAVEL.app.workspace.layout import CourseKey, Workspace
from GAVEL.app.workspace.manifest import load_manifest
from GAVEL.core.status import Status
from GAVEL.pages.download.viewmodel import (
    GRADEBOOK_DOWNLOAD,
    ROSTER_DOWNLOAD,
    DownloadViewModel,
    FocusCourseFolder,
    ShowError,
)
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_viewmodel_roster import wait_for_workers

TERMS = [TermInfo("2267", "Fall 2026", default=True)]
# The roster side: SER 401, session A. The Canvas side: SER 402, session C.
SER401_A = ClassSection("11111", "SER", "401", "Capstone I", "Gary", "TTh 1:30", session="A")
SER402 = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")

ROSTER_FOLDER = "ser401_26fa_11111"
CANVAS_FOLDER = "ser402_26fc_87275"


class GradebookCanvasClient(FakeCanvasClient):
    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        self.download_calls.append("fetch_gradebook_csv")
        return b"Student,ID\n"


@pytest.fixture
def roster() -> FakeRosterClient:
    return FakeRosterClient(terms=TERMS, sections=[SER401_A])


@pytest.fixture
def canvas() -> GradebookCanvasClient:
    return GradebookCanvasClient(courses=[SER402])


@pytest.fixture
def vm(qapp, roster, canvas, tmp_path: Path) -> DownloadViewModel:
    vm = DownloadViewModel(
        roster_client=roster,
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    vm.load_courses()
    vm.set_course_id(str(SER402.id))
    vm.set_term("2267")
    return vm


def search_ser401(qapp, vm: DownloadViewModel) -> None:
    vm.set_subject("SER")
    vm.set_catalog_number("401")
    vm.find_sections()
    wait_for_workers(qapp)
    vm.set_class_number(SER401_A.class_number)


def events(vm: DownloadViewModel) -> list:
    seen: list = []
    vm.event_raised.connect(seen.append)
    return seen


def course_folder(tmp_path: Path, name: str) -> Path:
    return tmp_path / "courses" / name


def test_preview_names_both_folders_when_the_selections_differ(qapp, vm):
    search_ser401(qapp, vm)
    state = vm.get_state()
    assert state.course_folder_name == f"courses/ser402_26fc_{SER401_A.class_number}"
    assert state.roster_folder_name == f"courses/{ROSTER_FOLDER}"
    assert state.roster_folder_error is None


def test_roster_goes_to_its_own_class_folder(qapp, vm, roster, tmp_path: Path):
    search_ser401(qapp, vm)
    vm.download_roster()
    wait_for_workers(qapp)

    assert roster.roster_requests == [RosterRequest(term="2267", class_number="11111")]
    expected = course_folder(tmp_path, ROSTER_FOLDER) / "original" / "roster.csv"
    assert vm.get_state().last_saved_path == str(expected)
    assert expected.exists()
    assert "SER 401" in vm.get_state().message
    assert not (tmp_path / "courses" / f"ser402_26fc_{SER401_A.class_number}").exists()


def test_roster_manifest_describes_the_roster_class(qapp, vm, tmp_path: Path):
    search_ser401(qapp, vm)
    vm.download_roster()
    wait_for_workers(qapp)

    manifest = load_manifest(
        Workspace(tmp_path).course(CourseKey.parse(ROSTER_FOLDER)).manifest_path
    )
    assert manifest.key == CourseKey("SER", "401", 2026, "f", "a", "11111")
    assert manifest.term_code == "2267"
    assert manifest.canvas_course_id is None
    assert [a.path for a in manifest.artifacts] == ["original/roster.csv"]


def test_gradebook_still_follows_the_canvas_course(qapp, vm, tmp_path: Path):
    search_ser401(qapp, vm)
    vm.download_roster()
    wait_for_workers(qapp)
    vm.download_gradebook()

    state = vm.get_state()
    canvas_folder = course_folder(tmp_path, f"ser402_26fc_{SER401_A.class_number}")
    assert state.last_saved_path == str(canvas_folder / "original" / "gradebook.csv")
    assert not (course_folder(tmp_path, ROSTER_FOLDER) / "original" / "gradebook.csv").exists()
    assert {ROSTER_DOWNLOAD, GRADEBOOK_DOWNLOAD} <= state.completed


def test_download_all_splits_the_roster_from_the_canvas_data(qapp, vm, tmp_path: Path, monkeypatch):
    # Without credentials the Gradescope step fails fast instead of opening a browser.
    monkeypatch.delenv("CANVAS_USERNAME", raising=False)
    monkeypatch.delenv("CANVAS_PASSWORD", raising=False)
    search_ser401(qapp, vm)
    vm.set_consent_quiz_id("101")
    vm.download_all()
    wait_for_workers(qapp)

    assert (course_folder(tmp_path, ROSTER_FOLDER) / "original" / "roster.csv").exists()
    canvas_folder = course_folder(tmp_path, f"ser402_26fc_{SER401_A.class_number}")
    assert (canvas_folder / "original" / "gradebook.csv").exists()
    assert not (canvas_folder / "original" / "roster.csv").exists()


def test_matching_selections_share_one_folder(qapp, vm, roster, tmp_path: Path):
    vm.set_class_number("87275")  # typed: the SER 402 course's own class
    assert vm.get_state().roster_folder_name == vm.get_state().course_folder_name
    vm.download_roster()
    wait_for_workers(qapp)
    vm.download_gradebook()

    folder = course_folder(tmp_path, CANVAS_FOLDER) / "original"
    assert (folder / "roster.csv").exists() and (folder / "gradebook.csv").exists()
    assert roster.roster_requests == [RosterRequest(term="2267", class_number="87275")]


def test_typed_class_outside_the_canvas_course_is_refused(vm, roster):
    vm.set_class_number("12345")
    state = vm.get_state()
    assert state.course_folder_name is not None  # Canvas downloads are unaffected
    assert state.roster_folder_name is None

    seen = events(vm)
    vm.download_roster()
    assert seen == [ShowError(state.roster_folder_error), FocusCourseFolder()]
    assert "Roster class 12345" in state.roster_folder_error
    assert vm.get_state().status is Status.CRITICAL
    assert roster.roster_requests == []


def test_typed_folder_name_still_takes_the_roster(qapp, vm, tmp_path: Path):
    vm.set_class_number("12345")
    vm.set_manual_course_folder("ser401_26fa_12345")
    vm.download_roster()
    wait_for_workers(qapp)
    assert (course_folder(tmp_path, "ser401_26fa_12345") / "original" / "roster.csv").exists()
