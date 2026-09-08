"""DownloadTab wiring for the Canvas course InputModeToggle.

Drives the real tab and view model against in-memory clients, offscreen.
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

# The view model sorts courses by course code, so SER334 lands first.
FIRST = CanvasCourse(id=209555, name="Operating Systems", course_code="SER334")
SECOND = CanvasCourse(id=213877, name="Capstone I", course_code="SER401")
COURSES = [SECOND, FIRST]  # deliberately unsorted on input
QUIZZES = [CanvasQuiz(id=11, name="Consent Quiz")]
ASSIGNMENTS = [CanvasAssignment(id=7, name="Homework 1")]
TYPED = 999999


def pump(qapp) -> None:
    """Let queued zero-delay timers (the tab's initial course load) fire."""
    for _ in range(5):
        qapp.processEvents()


def build(qapp, theme, tmp_path: Path) -> SimpleNamespace:
    canvas = FakeCanvasClient(courses=COURSES, quizzes=QUIZZES, assignments=ASSIGNMENTS)
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    tab = DownloadTab(theme, vm)
    pump(qapp)
    return SimpleNamespace(tab=tab, vm=vm, canvas=canvas, course=tab.course_input)


@pytest.fixture
def env(qapp, theme, tmp_path: Path, monkeypatch) -> SimpleNamespace:
    monkeypatch.setenv("CANVAS_TOKEN", "test-token")
    return build(qapp, theme, tmp_path)


def selected(env) -> str:
    return env.vm.get_state().selected_course_id


def test_courses_load_on_open_and_first_is_selected(env):
    assert env.canvas.list_courses_calls == 1
    assert env.course.mode() is InputMode.PICKER
    assert env.course.picker().combo.count() == 2
    assert selected(env) == str(FIRST.id)
    assert env.course.readout_text() == "SER334  Operating Systems  (209555)"
    assert env.course.picker().combo.itemText(1) == "SER401  Capstone I  (213877)"
    assert env.canvas.quiz_calls == [FIRST.id]
    assert env.canvas.assignment_calls == [FIRST.id]
    assert env.vm.get_state().can_download_gradebook


def test_only_one_course_input_is_visible_at_a_time(env):
    course = env.course
    assert course.picker().isVisibleTo(course)
    assert not course.manual_field().isVisibleTo(course)
    course.set_mode(InputMode.MANUAL)
    assert not course.picker().isVisibleTo(course)
    assert course.manual_field().isVisibleTo(course)


def test_picking_another_course_reloads_its_dependents(env):
    env.course.picker().combo.setCurrentIndex(1)
    assert selected(env) == str(SECOND.id)
    assert env.canvas.quiz_calls == [FIRST.id, SECOND.id]
    assert env.canvas.assignment_calls == [FIRST.id, SECOND.id]


def test_manual_id_is_stored_while_typing_but_committed_on_enter(env):
    course = env.course
    course.set_mode(InputMode.MANUAL)
    course.manual_field().setText(str(TYPED))
    assert selected(env) == str(TYPED)
    assert TYPED not in env.canvas.quiz_calls  # nothing fetched mid-typing

    course.manual_field().editingFinished.emit()
    assert env.canvas.quiz_calls[-1] == TYPED
    assert env.canvas.assignment_calls[-1] == TYPED


def test_focus_out_without_a_change_does_not_refetch(env):
    course = env.course
    course.set_mode(InputMode.MANUAL)
    course.manual_field().setText(str(TYPED))
    course.manual_field().editingFinished.emit()
    fetched = len(env.canvas.quiz_calls)
    course.manual_field().editingFinished.emit()
    assert len(env.canvas.quiz_calls) == fetched


def test_switching_to_manual_with_text_present_commits_it(env):
    course = env.course
    course.manual_field().setText(str(TYPED))  # typed earlier, hidden behind the picker
    assert selected(env) == str(FIRST.id)
    course.set_mode(InputMode.MANUAL)
    assert selected(env) == str(TYPED)
    assert env.canvas.quiz_calls[-1] == TYPED


def test_switching_back_to_picker_restores_its_selection(env):
    course = env.course
    course.picker().combo.setCurrentIndex(1)
    course.set_mode(InputMode.MANUAL)
    course.manual_field().setText(str(TYPED))
    course.set_mode(InputMode.PICKER)
    assert selected(env) == str(SECOND.id)


def test_invalid_manual_id_blocks_every_canvas_download(env):
    course = env.course
    course.set_mode(InputMode.MANUAL)
    course.manual_field().setText("abc")
    assert not course.is_valid()
    assert selected(env) == ""
    state = env.vm.get_state()
    assert not state.can_download_gradebook
    assert not state.can_download_consent
    assert not state.can_download_rubric
    assert not state.can_download_all_rubric_assessments
    assert not env.tab._download_gradebook_btn.isEnabled()
    assert env.canvas.quiz_calls == [FIRST.id]  # nothing fetched for the bad id


def test_reload_button_requests_the_course_list_again(env):
    env.course.picker().load_button.click()
    assert env.canvas.list_courses_calls == 2


def test_missing_token_forces_manual_mode_and_skips_loading(qapp, theme, tmp_path, monkeypatch):
    monkeypatch.delenv("CANVAS_TOKEN", raising=False)
    env = build(qapp, theme, tmp_path)
    assert env.course.mode() is InputMode.MANUAL
    assert env.canvas.list_courses_calls == 0
    env.course.set_mode(InputMode.PICKER)  # refused while the token is missing
    assert env.course.mode() is InputMode.MANUAL
