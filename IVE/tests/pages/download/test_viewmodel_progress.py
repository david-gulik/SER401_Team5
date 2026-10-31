"""Batch download progress, from the use case through DownloadViewModel to the tab."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.progress import DownloadProgress
from GAVEL.core.status import Status
from GAVEL.pages.download import tabs
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import QUIZ_REPORTS_DOWNLOAD, DownloadViewModel
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeRosterClient
from tests.pages.download.test_viewmodel_completion import (
    COURSE,
    OTHER,
    QUIZZES,
    GradebookCanvasClient,
)
from tests.pages.download.test_viewmodel_roster import wait_for_workers


@pytest.fixture
def canvas() -> GradebookCanvasClient:
    return GradebookCanvasClient(courses=[COURSE, OTHER], quizzes=QUIZZES)


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
    wait_for_workers(qapp)
    vm.set_course_id(str(COURSE.id))
    return vm


def record_states(vm: DownloadViewModel) -> list:
    states: list = []
    vm.state_changed.connect(states.append)
    return states


def test_quiz_progress_reaches_the_view_model_as_each_quiz_finishes(qapp, vm, canvas):
    canvas.unavailable_quiz_ids = {QUIZZES[1].id}  # a skipped quiz still counts
    states = record_states(vm)

    vm.download_all_quizzes()
    wait_for_workers(qapp)

    progress = [s.progress for s in states if s.progress is not None]
    assert progress[0].label == f"Listing quizzes for course {COURSE.id}"
    assert [(p.done, p.total) for p in progress] == [(0, 0), (0, 2), (1, 2), (2, 2)]
    assert "Downloading quizzes 1 of 2. Last finished: Quiz One" in [s.message for s in states]


def test_finished_download_clears_progress_and_shows_totals(qapp, vm):
    vm.download_all_quizzes()
    wait_for_workers(qapp)

    state = vm.get_state()
    assert not state.is_busy
    assert state.progress is None
    assert "2 saved" in state.message
    assert "0 skipped, 0 failed" in state.message


def test_progress_after_the_download_finished_is_ignored(qapp, vm):
    vm.download_all_quizzes()
    wait_for_workers(qapp)
    finished = vm.get_state()

    vm._on_progress(DownloadProgress("Downloading quizzes", 1, 2, "Quiz One"))

    assert vm.get_state() == finished


def test_rubric_batch_reports_each_assignment(qapp, vm):
    vm.set_assignment_ids("7,9")
    states = record_states(vm)

    vm.download_rubric_assessment()
    wait_for_workers(qapp)

    progress = [s.progress for s in states if s.progress is not None]
    assert [(p.done, p.total) for p in progress] == [(0, 2), (1, 2), (2, 2)]
    assert [p.item for p in progress[1:]] == ["7", "9"]


def test_download_all_tags_progress_with_its_step(qapp, vm, monkeypatch):
    # Without credentials the Gradescope step fails fast instead of opening a browser.
    monkeypatch.delenv("CANVAS_USERNAME", raising=False)
    monkeypatch.delenv("CANVAS_PASSWORD", raising=False)
    vm.set_term("2267")
    vm.set_class_number("87275")
    vm.set_consent_quiz_id("11")
    states = record_states(vm)

    vm.download_all()
    wait_for_workers(qapp)

    texts = [s.progress.text for s in states if s.progress is not None]
    assert texts[:2] == ["Starting Download All", "Step 1 of 6: Roster"]
    assert f"Step 5 of 6: {QUIZ_REPORTS_DOWNLOAD}" in texts
    assert "Step 5 of 6: Downloading quizzes 2 of 2" in texts
    assert "Step 6 of 6: Rubric Assessment" in texts
    assert vm.get_state().progress is None


def test_tab_shows_the_panel_while_busy_and_hides_it_after(qapp, theme, vm, monkeypatch):
    monkeypatch.setattr(tabs, "show_message", lambda *a, **k: None)
    tab = DownloadTab(theme, vm)
    wait_for_workers(qapp)  # the tab's own startup loads
    panel = tab.progress_panel
    shown: list[tuple[bool, str, str]] = []
    vm.state_changed.connect(
        lambda _state: shown.append((panel.isVisibleTo(tab), panel.title_text, panel.count_text))
    )

    vm.download_all_quizzes()
    wait_for_workers(qapp)

    assert shown[0] == (True, f"Listing quizzes for course {COURSE.id}", "")
    assert (True, "Downloading quizzes", "1 of 2") in shown
    assert (True, "Downloading quizzes", "2 of 2") in shown
    assert not panel.isVisibleTo(tab)


def test_quick_work_spins_the_busy_bar_without_the_panel(qapp, theme, vm):
    tab = DownloadTab(theme, vm)
    wait_for_workers(qapp)  # the tab's own startup loads
    seen: list[tuple[bool, bool]] = []
    vm.state_changed.connect(
        lambda state: (
            seen.append((tab.progress_panel.isVisibleTo(tab), tab._busy_bar.isVisibleTo(tab)))
            if state.is_busy
            else None
        )
    )

    vm.load_quizzes(str(COURSE.id))
    wait_for_workers(qapp)

    assert seen and all(seen_state == (False, True) for seen_state in seen)


@pytest.mark.parametrize(
    ("start", "label"),
    [
        ("download_gradebook", f"Downloading gradebook for course {COURSE.id}"),
        ("download_consent", f"Downloading consent form for course {COURSE.id}"),
    ],
)
def test_single_file_downloads_run_in_the_background_with_the_panel(qapp, vm, start, label):
    vm.set_consent_quiz_id("11")

    getattr(vm, start)()

    # Still running when the call returns: the window stays responsive meanwhile.
    state = vm.get_state()
    assert state.is_busy
    assert state.progress is not None and state.progress.label == label
    wait_for_workers(qapp)
    assert not vm.get_state().is_busy
    assert vm.get_state().progress is None


def test_picking_a_course_loads_quizzes_and_assignments_in_one_background_job(qapp, vm, canvas):
    canvas.assignments = [CanvasAssignment(id=7, name="Homework 1")]

    vm.load_course_lists(str(COURSE.id))

    assert vm.get_state().is_busy  # still loading when the call returns
    wait_for_workers(qapp)
    state = vm.get_state()
    assert [q.id for q in state.quizzes] == [q.id for q in QUIZZES]
    assert [a.id for a in state.assignments] == [7]
    assert state.message == "Loaded 2 quiz(zes). Loaded 1 assignment(s)."


def test_a_failed_quiz_list_still_loads_assignments_and_shows_the_error(qapp, vm, canvas):
    canvas.assignments = [CanvasAssignment(id=7, name="Homework 1")]

    def broken(course_id):
        raise RuntimeError("401 Unauthorized")

    canvas.list_quizzes = broken

    vm.load_course_lists(str(COURSE.id))
    wait_for_workers(qapp)

    state = vm.get_state()
    assert [a.id for a in state.assignments] == [7]
    assert state.status is Status.CRITICAL
    assert state.message == "401 Unauthorized"


def test_course_list_loads_in_the_background(qapp, vm, canvas):
    vm.load_courses()

    assert vm.get_state().is_busy
    wait_for_workers(qapp)
    assert {c.id for c in vm.get_state().courses} == {COURSE.id, OTHER.id}
