"""DownloadTab check marks and the reminder before leaving a half-downloaded course."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QMessageBox

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.pages.download.tabs import DONE_MARK, DownloadTab
from GAVEL.pages.download.viewmodel import (
    GRADEBOOK_DOWNLOAD,
    ROSTER_DOWNLOAD,
    DownloadViewModel,
)
from GAVEL.services.logger import AppLogger
from GAVEL.ui_components.input_mode_toggle import InputMode
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_viewmodel_roster import wait_for_workers

FIRST = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")
SECOND = CanvasCourse(id=250417, name="SER 401", course_code="2026SpringC-X-SER401-37789")


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
    canvas = GradebookCanvasClient(courses=[SECOND, FIRST])
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    tab = DownloadTab(theme, vm)
    pump(qapp)
    answers: list[bool] = []
    prompts: list[str] = []

    def fake_confirm(state) -> bool:
        prompts.append(state.selected_course_id)
        return answers.pop(0)

    monkeypatch.setattr(tab, "_confirm_course_switch", fake_confirm)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    return SimpleNamespace(
        tab=tab,
        vm=vm,
        canvas=canvas,
        combo=tab.course_input.picker().combo,
        answers=answers,
        prompts=prompts,
    )


def selected(env) -> str:
    return env.vm.get_state().selected_course_id


def test_buttons_start_without_a_mark(env):
    for name in (ROSTER_DOWNLOAD, GRADEBOOK_DOWNLOAD):
        assert DONE_MARK not in env.tab.download_button(name).text()


def test_gradebook_button_earns_a_mark_after_success(env):
    env.tab.download_button(GRADEBOOK_DOWNLOAD).click()
    assert env.tab.download_button(GRADEBOOK_DOWNLOAD).text() == f"Download Gradebook {DONE_MARK}"


def test_roster_button_earns_a_mark_and_loses_it_on_a_new_class(qapp, env):
    env.vm.set_term("2267")
    env.vm.set_class_number("37789")
    env.tab.download_button(ROSTER_DOWNLOAD).click()
    wait_for_workers(qapp)
    assert env.tab.download_button(ROSTER_DOWNLOAD).text() == f"Download Roster {DONE_MARK}"

    env.vm.set_class_number("12345")
    assert env.tab.download_button(ROSTER_DOWNLOAD).text() == "Download Roster"


def test_no_prompt_when_nothing_was_downloaded(env):
    env.combo.setCurrentIndex(1)
    assert env.prompts == []
    assert selected(env) == str(SECOND.id)


def test_declining_the_prompt_keeps_the_course_and_its_marks(env):
    env.tab.download_button(GRADEBOOK_DOWNLOAD).click()
    fetched = len(env.canvas.quiz_calls)
    env.answers.append(False)

    env.combo.setCurrentIndex(1)

    assert env.prompts == [str(FIRST.id)]
    assert selected(env) == str(FIRST.id)
    assert env.combo.currentData() == str(FIRST.id)
    assert env.tab.course_input.value() == str(FIRST.id)
    assert DONE_MARK in env.tab.download_button(GRADEBOOK_DOWNLOAD).text()
    assert len(env.canvas.quiz_calls) == fetched  # nothing reloaded


def test_accepting_the_prompt_switches_and_clears_the_marks(env):
    env.tab.download_button(GRADEBOOK_DOWNLOAD).click()
    env.answers.append(True)

    env.combo.setCurrentIndex(1)

    assert env.prompts == [str(FIRST.id)]
    assert selected(env) == str(SECOND.id)
    assert env.canvas.quiz_calls[-1] == SECOND.id
    assert DONE_MARK not in env.tab.download_button(GRADEBOOK_DOWNLOAD).text()


def test_declining_once_does_not_stop_a_later_switch(env):
    env.tab.download_button(GRADEBOOK_DOWNLOAD).click()
    env.answers.extend([False, True])
    env.combo.setCurrentIndex(1)
    assert selected(env) == str(FIRST.id)
    env.combo.setCurrentIndex(1)
    assert selected(env) == str(SECOND.id)
    assert env.prompts == [str(FIRST.id), str(FIRST.id)]


def test_manual_mode_never_prompts(env):
    env.tab.download_button(GRADEBOOK_DOWNLOAD).click()
    env.tab.course_input.set_mode(InputMode.MANUAL)
    env.tab.course_input.manual_field().setText("999999")
    assert env.prompts == []
    assert selected(env) == "999999"


def test_reloading_courses_does_not_prompt(env):
    env.tab.download_button(GRADEBOOK_DOWNLOAD).click()
    env.tab.course_input.picker().load_button.click()
    assert env.prompts == []
    assert selected(env) == str(FIRST.id)
    assert DONE_MARK in env.tab.download_button(GRADEBOOK_DOWNLOAD).text()
