from __future__ import annotations

import zipfile

from GAVEL.bootstrap import build_dataset_readers
from GAVEL.core.background import run_now
from GAVEL.pages.stability_check.tabs import AUTOGRADERS_SHOWN, StabilityCheckTab
from GAVEL.pages.stability_check.viewmodel import Phase, StabilityCheckViewModel
from tests.fakes.autograder_runner import FakeAutograderRunner, completed


def _tab(theme, workspace, runner=None):
    vm = StabilityCheckViewModel(
        dataset_readers=build_dataset_readers(),
        workspace=workspace,
        runner=runner or FakeAutograderRunner(default=completed({"Adds": (2.0, 2.0)})),
        background=run_now,
        workers=4,
    )
    return StabilityCheckTab(theme, vm), vm


def _autograders(tab) -> list[str]:
    return [tab.autograder_list.item(i).text() for i in range(tab.autograder_list.count())]


def _shown_autograders(tab) -> list[str]:
    items = [tab.autograder_list.item(i) for i in range(tab.autograder_list.count())]
    return [item.text() for item in items if not item.isHidden()]


def _pick_autograder(tab, name: str) -> None:
    tab.autograder_list.setCurrentRow(_autograders(tab).index(name))


def test_the_tab_waits_for_a_course(qapp, theme, workspace):
    tab, vm = _tab(theme, workspace)

    assert tab.assignment_combo.count() == 1
    assert not tab.assignment_combo.isEnabled()
    assert not tab.run_button.isEnabled()
    assert tab.run_button.toolTip() == "Choose a course"
    assert tab.status_label.text() == "Choose a course to run a check."
    assert tab.runs_spin.value() == 10
    assert tab.timeout_spin.value() == 5
    assert tab.workers_spin.value() == 4

    tab.deleteLater()


def test_picking_through_the_widgets_reaches_the_viewmodel(qapp, theme, workspace, course):
    tab, vm = _tab(theme, workspace)
    tab.set_course(course)

    assert tab.assignment_combo.count() == 3
    assert tab.assignment_combo.itemText(2) == "Module 9"
    assert tab.run_button.toolTip() == "Choose an assignment"

    tab.assignment_combo.setCurrentIndex(2)

    assert vm.state.module is not None and vm.state.module.module_number == 9
    assert _autograders(tab) == ["folder_grader", "zipped_grader"]
    assert tab.autograder_list.currentRow() == -1
    assert tab.autograder_list.property("role") == "picker_list", "styled by the theme"
    assert tab.run_button.toolTip() == "Choose an autograder"

    _pick_autograder(tab, "folder_grader")

    assert vm.state.autograder is not None and vm.state.autograder.name == "folder_grader"
    assert tab.run_button.isEnabled()
    assert tab.run_button.toolTip() == ""
    assert tab.estimate_label.text().startswith("3 submissions × 10 runs = 30 executions")

    tab.runs_spin.setValue(20)
    tab.timeout_spin.setValue(2)
    tab.workers_spin.setValue(2)

    assert (vm.state.runs, vm.state.timeout_minutes, vm.state.workers) == (20, 2, 2)
    assert tab.estimate_label.text().startswith("3 submissions × 20 runs = 60 executions")

    tab.deleteLater()


def test_the_filter_narrows_the_list_without_losing_the_pick(qapp, theme, workspace, course):
    tab, vm = _tab(theme, workspace)
    tab.set_course(course)
    tab.assignment_combo.setCurrentIndex(2)
    _pick_autograder(tab, "folder_grader")

    tab.autograder_filter.setText("ZIP")

    assert _shown_autograders(tab) == ["zipped_grader"]
    assert vm.state.autograder is not None and vm.state.autograder.name == "folder_grader"
    assert tab.run_button.isEnabled()

    tab.runs_spin.setValue(3)

    assert tab.autograder_filter.text() == "ZIP", "a settings change keeps the filter"

    tab.autograder_filter.clear()

    assert _shown_autograders(tab) == ["folder_grader", "zipped_grader"]
    assert tab.autograder_list.currentRow() == 0

    tab.deleteLater()


def test_a_long_list_stops_growing_and_scrolls(qapp, theme, workspace, course):
    tab, vm = _tab(theme, workspace)
    tab.set_course(course)
    tab.assignment_combo.setCurrentIndex(2)
    row_height = tab.autograder_list.sizeHintForRow(0)
    frame = 2 * tab.autograder_list.frameWidth()

    assert tab.autograder_list.count() == 2
    assert tab.autograder_list.maximumHeight() == 2 * row_height + frame

    root = workspace.course_autograders_dir(course.key)
    for index in range(AUTOGRADERS_SHOWN + 2):
        with zipfile.ZipFile(root / f"grader_v{index:02d}.zip", "w") as archive:
            archive.writestr("config.json", "{}")
    tab.assignment_combo.setCurrentIndex(1)
    tab.assignment_combo.setCurrentIndex(2)

    assert tab.autograder_list.count() == AUTOGRADERS_SHOWN + 4
    assert tab.autograder_list.maximumHeight() == AUTOGRADERS_SHOWN * row_height + frame

    tab.deleteLater()


def test_a_finished_check_shows_the_results_card(qapp, theme, workspace, course):
    tab, vm = _tab(theme, workspace)
    tab.set_course(course)
    tab.assignment_combo.setCurrentIndex(2)
    _pick_autograder(tab, "folder_grader")
    tab.runs_spin.setValue(2)

    tab.run_button.click()

    assert vm.state.phase is Phase.DONE
    assert not tab._running_card.isVisibleTo(tab)
    assert tab._results_card.isVisibleTo(tab)
    assert tab.verdict_label.text().startswith("Stable")
    assert tab.results_list.count() == 1
    assert tab.results_list.item(0).text() == "No unstable tests."
    assert tab.saved_label.text().startswith("Saved to ")
    assert tab.run_button.isEnabled()
    assert tab.previous_note.text().startswith("Last checked")

    tab.deleteLater()


def test_unstable_tests_are_listed_worst_first(qapp, theme, workspace, course):
    def script(name, index):
        if name == "anon_4821" and index == 1:
            return completed({"Adds": (0.0, 2.0)})
        return completed({"Adds": (2.0, 2.0)})

    tab, vm = _tab(theme, workspace, FakeAutograderRunner(script))
    tab.set_course(course)
    tab.assignment_combo.setCurrentIndex(2)
    _pick_autograder(tab, "folder_grader")
    tab.runs_spin.setValue(2)

    tab.run_button.click()

    assert tab.verdict_label.text().startswith("Unstable")
    assert tab.results_list.item(0).text() == (
        "Changed · Adds · 5/6 runs agreed · 1 of 3 submissions"
    )

    tab.deleteLater()


def test_changing_course_clears_the_picks(qapp, theme, workspace, course):
    tab, vm = _tab(theme, workspace)
    tab.set_course(course)
    tab.assignment_combo.setCurrentIndex(2)
    _pick_autograder(tab, "folder_grader")

    tab.set_course(None)

    assert tab.assignment_combo.count() == 1
    assert _autograders(tab) == []
    assert not tab.autograder_list.isVisibleTo(tab)
    assert tab.autograder_placeholder.text() == "Pick an assignment to see its autograders."
    assert not tab.run_button.isEnabled()

    tab.deleteLater()
