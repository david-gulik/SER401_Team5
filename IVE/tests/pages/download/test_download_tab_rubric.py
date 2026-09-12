"""DownloadTab wiring for the rubric assignment InputModeToggle.

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
QUIZZES = [CanvasQuiz(id=11, name="Research Consent")]
# The view model sorts by name, so Homework 1 lands first.
HOMEWORK = CanvasAssignment(id=7, name="Homework 1")
PROJECT = CanvasAssignment(id=9, name="Project Report")
ASSIGNMENTS = [PROJECT, HOMEWORK]  # deliberately unsorted on input
TYPED = "7216983, 7216990"


def pump(qapp) -> None:
    for _ in range(5):
        qapp.processEvents()


def build(qapp, theme, tmp_path: Path) -> SimpleNamespace:
    canvas = FakeCanvasClient(courses=[COURSE], quizzes=QUIZZES, assignments=ASSIGNMENTS)
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    tab = DownloadTab(theme, vm)
    pump(qapp)
    return SimpleNamespace(
        tab=tab, vm=vm, canvas=canvas, rubric=tab.assignment_input, picker=tab._assignment_picker
    )


@pytest.fixture
def env(qapp, theme, tmp_path: Path, monkeypatch) -> SimpleNamespace:
    monkeypatch.setenv("CANVAS_TOKEN", "test-token")
    return build(qapp, theme, tmp_path)


def assignment_ids(env) -> str:
    return env.vm.get_state().assignment_ids


def test_only_one_assignment_input_is_visible_at_a_time(env):
    rubric = env.rubric
    assert rubric.mode() is InputMode.PICKER
    assert rubric.picker().isVisibleTo(rubric)
    assert not rubric.manual_field().isVisibleTo(rubric)
    rubric.set_mode(InputMode.MANUAL)
    assert not rubric.picker().isVisibleTo(rubric)
    assert rubric.manual_field().isVisibleTo(rubric)


def test_both_download_buttons_sit_inside_the_rubric_panel(env):
    assert env.rubric.isAncestorOf(env.tab._download_rubric_btn)
    assert env.rubric.isAncestorOf(env.tab._download_all_rubric_btn)


def test_assignments_load_with_the_course_and_none_is_preselected(env):
    assert env.canvas.assignment_calls == [COURSE.id]
    boxes = env.picker.boxes()
    assert [b.text() for b in boxes] == ["Homework 1  (7)", "Project Report  (9)"]
    assert not any(b.isChecked() for b in boxes)
    assert assignment_ids(env) == ""
    assert env.rubric.readout_text() == env.rubric.EMPTY_PICKER_TEXT
    assert not env.tab._download_rubric_btn.isEnabled()
    assert env.tab._download_all_rubric_btn.isEnabled()  # needs only a course


def test_checking_assignments_joins_their_ids_in_list_order(env):
    boxes = env.picker.boxes()
    boxes[1].setChecked(True)
    assert assignment_ids(env) == "9"
    assert env.tab._download_rubric_btn.isEnabled()
    boxes[0].setChecked(True)
    assert assignment_ids(env) == "7,9"
    assert env.rubric.readout_text() == "Homework 1  (7), Project Report  (9)"


def test_select_all_and_clear_buttons_drive_the_view_model(env):
    env.picker.select_all_button.click()
    assert assignment_ids(env) == "7,9"
    env.picker.clear_button.click()
    assert assignment_ids(env) == ""
    assert not env.tab._download_rubric_btn.isEnabled()


def test_manual_comma_separated_ids_are_used_when_valid(env):
    env.rubric.set_mode(InputMode.MANUAL)
    env.rubric.manual_field().setText(TYPED)
    assert env.rubric.is_valid()
    assert assignment_ids(env) == TYPED
    assert env.tab._download_rubric_btn.isEnabled()


def test_invalid_manual_ids_block_the_rubric_download(env):
    env.rubric.set_mode(InputMode.MANUAL)
    env.rubric.manual_field().setText("7216983, abc")
    assert not env.rubric.is_valid()
    assert assignment_ids(env) == ""
    assert not env.tab._download_rubric_btn.isEnabled()


def test_switching_modes_swaps_the_resolved_ids(env):
    env.picker.boxes()[0].setChecked(True)
    env.rubric.set_mode(InputMode.MANUAL)
    env.rubric.manual_field().setText(TYPED)
    assert assignment_ids(env) == TYPED
    env.rubric.set_mode(InputMode.PICKER)
    assert assignment_ids(env) == "7"


def test_reload_button_fetches_assignments_for_the_current_course(env):
    env.picker.load_button.click()
    assert env.canvas.assignment_calls == [COURSE.id, COURSE.id]


def test_reload_keeps_the_checked_assignments(env):
    env.picker.boxes()[1].setChecked(True)
    env.canvas.assignments = [HOMEWORK, PROJECT, CanvasAssignment(id=12, name="Quiz 3")]
    env.picker.load_button.click()
    assert env.picker.count() == 3
    assert assignment_ids(env) == "9"


def test_changing_course_clears_the_assignment_list_and_choice(env):
    env.picker.boxes()[0].setChecked(True)
    env.tab.course_input.set_mode(InputMode.MANUAL)
    env.tab.course_input.manual_field().setText("999999")
    assert env.picker.count() == 0
    assert assignment_ids(env) == ""
    assert env.rubric.readout_text() == env.rubric.EMPTY_PICKER_TEXT


def test_missing_token_forces_manual_assignment_entry(qapp, theme, tmp_path, monkeypatch):
    monkeypatch.delenv("CANVAS_TOKEN", raising=False)
    env = build(qapp, theme, tmp_path)
    assert env.rubric.mode() is InputMode.MANUAL
    env.rubric.set_mode(InputMode.PICKER)  # refused while the token is missing
    assert env.rubric.mode() is InputMode.MANUAL


def test_assignments_without_a_rubric_are_flagged_in_the_list(env):
    env.canvas.assignments = [
        HOMEWORK,
        PROJECT,
        CanvasAssignment(id=12, name="Quiz 3", has_rubric=False),
    ]
    env.picker.load_button.click()
    boxes = env.picker.boxes()
    assert [b.text() for b in boxes] == [
        "Homework 1  (7)",
        "Project Report  (9)",
        "⚠ Quiz 3  (12)",
    ]
    assert boxes[0].toolTip() == ""
    assert "No rubric attached" in boxes[2].toolTip()
