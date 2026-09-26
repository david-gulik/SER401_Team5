"""DownloadTab wiring for the course folder preview, its manual override, and focus."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QMessageBox

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import GRADEBOOK_DOWNLOAD, DownloadViewModel
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

SIS_COURSE = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")
TRAINING = CanvasCourse(id=213877, name="IVE Capstone", course_code="TRN-2026Spring-IVECapstone")


class GradebookCanvasClient(FakeCanvasClient):
    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        self.download_calls.append("fetch_gradebook_csv")
        return b"Student,ID\n"


def pump(qapp) -> None:
    for _ in range(5):
        qapp.processEvents()


@pytest.fixture
def env(qapp, theme, tmp_path: Path, monkeypatch) -> SimpleNamespace:
    monkeypatch.setenv("CANVAS_TOKEN", "test-token")
    dialogs: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: dialogs.append("info"))
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: dialogs.append("error"))
    canvas = GradebookCanvasClient(courses=[SIS_COURSE, TRAINING])
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    tab = DownloadTab(theme, vm)
    tab.show()
    pump(qapp)
    vm.load_courses()
    pump(qapp)
    return SimpleNamespace(
        tab=tab, vm=vm, canvas=canvas, label=tab._course_folder_label, dialogs=dialogs
    )


def test_preview_explains_when_nothing_is_selected(env):
    env.vm.set_course_id("")  # loading the list selects its first course
    assert env.label.text().startswith("Course folder: Select a Canvas course")


def test_preview_shows_the_folder_for_an_sis_course(env):
    env.vm.set_course_id(str(SIS_COURSE.id))
    assert env.label.text() == "Course folder: courses/ser402_26fc_87275"


def test_preview_explains_a_training_course(env):
    env.vm.set_course_id(str(TRAINING.id))
    assert "no ASU course code" in env.label.text()


def test_typing_an_override_updates_state_and_preview(env):
    env.vm.set_course_id(str(TRAINING.id))
    env.tab.course_folder_input.setText("ser401_26f_99999")
    env.tab.course_folder_input.textEdited.emit("ser401_26f_99999")  # setText does not fire it
    assert env.vm.get_state().manual_course_folder == "ser401_26f_99999"
    assert env.label.text() == "Course folder: courses/ser401_26f_99999"


def test_malformed_override_is_explained_in_the_preview(env):
    env.tab.course_folder_input.textEdited.emit("ser222_25xc_12345")
    assert env.label.text().startswith(
        "Course folder: 'ser222_25xc_12345' is not a valid course folder name"
    )
    assert "term letter (s Spring, u Summer, f Fall, w Winter)" in env.label.text()


def test_state_changes_are_reflected_in_the_field(env):
    env.vm.set_manual_course_folder("ser401_26f_99999")
    assert env.tab.course_folder_input.text() == "ser401_26f_99999"
    env.vm.set_manual_course_folder("")
    assert env.tab.course_folder_input.text() == ""


class TestFocus:
    def test_naming_failure_focuses_the_override_field(self, env):
        env.vm.set_course_id(str(TRAINING.id))
        button = env.tab.download_button(GRADEBOOK_DOWNLOAD)
        button.setFocus()
        assert env.tab.focusWidget() is button

        button.click()

        assert env.dialogs == ["error"]
        assert env.tab.focusWidget() is env.tab.course_folder_input
        assert env.canvas.download_calls == []

    def test_focus_stays_on_the_clicked_button_through_a_download(self, env):
        env.vm.set_course_id(str(SIS_COURSE.id))
        button = env.tab.download_button(GRADEBOOK_DOWNLOAD)
        button.setFocus()

        button.click()

        assert env.dialogs == ["info"]
        assert env.canvas.download_calls == ["fetch_gradebook_csv"]
        assert button.isEnabled()
        assert env.tab.focusWidget() is button

    def test_busy_state_parks_focus_instead_of_jumping(self, env):
        env.vm.set_course_id(str(SIS_COURSE.id))
        button = env.tab.download_button(GRADEBOOK_DOWNLOAD)
        button.setFocus()

        env.vm._set_busy("working...")  # what every download does first

        assert not button.isEnabled()
        assert env.tab.focusWidget() is env.tab._focus_anchor

        env.vm._set_idle(env.vm.get_state().status, "done")

        assert env.tab.focusWidget() is button
