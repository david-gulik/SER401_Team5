"""DownloadTab wiring for the "Select File Uploads" / "Download Submission Files" controls.

Covers the download button's placement and enabled state. The "Select
File Uploads" button checks only assignments that accept a file upload.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasCourse
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import DownloadViewModel
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_download_tab_rubric import pump

COURSE = CanvasCourse(id=213877, name="Capstone I", course_code="SER401")
ADJ_1 = CanvasAssignment(id=7, name="ADJ 1", submission_types=("online_upload",))
ADJ_2 = CanvasAssignment(id=9, name="ADJ 2", submission_types=("online_upload",))
GRADESCOPE_HW = CanvasAssignment(
    id=12, name="Homework (Gradescope)", submission_types=("external_tool",)
)
ASSIGNMENTS = [GRADESCOPE_HW, ADJ_1, ADJ_2]


def build(qapp, theme, tmp_path: Path) -> SimpleNamespace:
    canvas = FakeCanvasClient(courses=[COURSE], assignments=ASSIGNMENTS)
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    tab = DownloadTab(theme, vm)
    pump(qapp)
    return SimpleNamespace(tab=tab, vm=vm, canvas=canvas, picker=tab._assignment_picker)


@pytest.fixture
def env(qapp, theme, tmp_path: Path, monkeypatch) -> SimpleNamespace:
    monkeypatch.setenv("CANVAS_TOKEN", "test-token")
    return build(qapp, theme, tmp_path)


def assignment_ids(env) -> str:
    return env.vm.get_state().assignment_ids


def test_download_button_sits_inside_the_shared_panel(env):
    assert env.tab.assignment_input.isAncestorOf(env.tab._download_submissions_btn)


def test_download_button_disabled_until_an_assignment_is_selected(env):
    assert not env.tab._download_submissions_btn.isEnabled()
    env.picker.boxes()[0].setChecked(True)
    assert env.tab._download_submissions_btn.isEnabled()


def test_select_file_uploads_checks_only_online_upload_assignments(qapp, env):
    # The picker sorts alphabetically by name: ADJ 1, ADJ 2, Homework (Gradescope).
    env.picker.boxes()[2].setChecked(True)  # Homework (Gradescope), no file upload
    assert env.picker.isAncestorOf(env.tab._select_file_uploads_btn)

    env.tab._select_file_uploads_btn.click()

    boxes = env.picker.boxes()
    assert [b.text() for b in boxes] == [
        "ADJ 1  (7)",
        "ADJ 2  (9)",
        "Homework (Gradescope)  (12)",
    ]
    assert [b.isChecked() for b in boxes] == [True, True, False]
    assert assignment_ids(env) == "7,9"
    assert env.tab._download_submissions_btn.isEnabled()


def test_select_file_uploads_is_disabled_until_assignments_load(qapp, theme, tmp_path, monkeypatch):
    monkeypatch.delenv("CANVAS_TOKEN", raising=False)
    env = build(qapp, theme, tmp_path)
    assert env.picker.count() == 0
    assert not env.tab._select_file_uploads_btn.isEnabled()
