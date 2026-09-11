"""DownloadTab wiring for the consent quiz InputModeToggle.

Drives the real tab and view model against in-memory clients, offscreen.
Download actions are never triggered here: they end in a modal dialog.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasCourse, CanvasQuiz
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import DownloadViewModel
from GAVEL.services.logger import AppLogger
from GAVEL.ui_components.input_mode_toggle import InputMode
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

COURSE = CanvasCourse(id=213877, name="Capstone I", course_code="SER401")
# Sorted by name the attendance quiz comes first; the consent quiz must still win.
ATTENDANCE = CanvasQuiz(id=5, name="Attendance Quiz")
CONSENT = CanvasQuiz(id=11, name="Research Consent")
ASSIGNMENTS = [CanvasAssignment(id=7, name="Homework 1")]
TYPED = "7777777"


def pump(qapp) -> None:
    for _ in range(5):
        qapp.processEvents()


def build(qapp, theme, tmp_path: Path, quizzes=(ATTENDANCE, CONSENT)) -> SimpleNamespace:
    canvas = FakeCanvasClient(courses=[COURSE], quizzes=list(quizzes), assignments=ASSIGNMENTS)
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    tab = DownloadTab(theme, vm)
    pump(qapp)
    return SimpleNamespace(tab=tab, vm=vm, canvas=canvas, quiz=tab.quiz_input)


@pytest.fixture
def env(qapp, theme, tmp_path: Path, monkeypatch) -> SimpleNamespace:
    monkeypatch.setenv("CANVAS_TOKEN", "test-token")
    return build(qapp, theme, tmp_path)


def quiz_id(env) -> str:
    return env.vm.get_state().selected_consent_quiz_id


def test_only_one_quiz_input_is_visible_at_a_time(env):
    quiz = env.quiz
    assert quiz.mode() is InputMode.PICKER
    assert quiz.picker().isVisibleTo(quiz)
    assert not quiz.manual_field().isVisibleTo(quiz)
    quiz.set_mode(InputMode.MANUAL)
    assert not quiz.picker().isVisibleTo(quiz)
    assert quiz.manual_field().isVisibleTo(quiz)


def test_download_button_sits_inside_the_quiz_panel(env):
    assert env.quiz.isAncestorOf(env.tab._download_consent_btn)


def test_quizzes_load_with_the_course_and_the_consent_quiz_is_preselected(env):
    assert env.canvas.quiz_calls == [COURSE.id]
    combo = env.quiz.picker().combo
    assert combo.count() == 2
    assert combo.itemText(0) == "Attendance Quiz  (5)"  # sorted by name, ID shown
    assert quiz_id(env) == str(CONSENT.id)
    assert env.quiz.readout_text() == "Research Consent  (11)"
    assert env.tab._download_consent_btn.isEnabled()


def test_first_quiz_is_selected_when_none_mentions_consent(qapp, theme, tmp_path, monkeypatch):
    monkeypatch.setenv("CANVAS_TOKEN", "test-token")
    env = build(qapp, theme, tmp_path, quizzes=(ATTENDANCE, CanvasQuiz(id=9, name="Final Survey")))
    assert quiz_id(env) == str(ATTENDANCE.id)


def test_picking_another_quiz_updates_the_view_model(env):
    env.quiz.picker().combo.setCurrentIndex(0)
    assert quiz_id(env) == str(ATTENDANCE.id)


def test_manual_quiz_id_is_used_when_valid(env):
    env.quiz.set_mode(InputMode.MANUAL)
    env.quiz.manual_field().setText(TYPED)
    assert env.quiz.is_valid()
    assert quiz_id(env) == TYPED
    assert env.tab._download_consent_btn.isEnabled()


def test_invalid_manual_quiz_id_blocks_the_consent_download(env):
    env.quiz.set_mode(InputMode.MANUAL)
    env.quiz.manual_field().setText("abc")
    assert not env.quiz.is_valid()
    assert quiz_id(env) == ""
    assert not env.tab._download_consent_btn.isEnabled()


def test_switching_modes_swaps_the_resolved_quiz_id(env):
    env.quiz.set_mode(InputMode.MANUAL)
    env.quiz.manual_field().setText(TYPED)
    assert quiz_id(env) == TYPED
    env.quiz.set_mode(InputMode.PICKER)
    assert quiz_id(env) == str(CONSENT.id)


def test_reload_button_fetches_quizzes_for_the_current_course(env):
    env.quiz.picker().load_button.click()
    assert env.canvas.quiz_calls == [COURSE.id, COURSE.id]


def test_changing_course_clears_the_quiz_list_and_choice(env):
    env.tab.course_input.set_mode(InputMode.MANUAL)
    env.tab.course_input.manual_field().setText("999999")
    assert env.quiz.picker().combo.count() == 0
    assert quiz_id(env) == ""
    assert env.quiz.readout_text() == env.quiz.EMPTY_PICKER_TEXT


def test_missing_token_forces_manual_quiz_entry(qapp, theme, tmp_path, monkeypatch):
    monkeypatch.delenv("CANVAS_TOKEN", raising=False)
    env = build(qapp, theme, tmp_path)
    assert env.quiz.mode() is InputMode.MANUAL
    env.quiz.set_mode(InputMode.PICKER)  # refused while the token is missing
    assert env.quiz.mode() is InputMode.MANUAL
