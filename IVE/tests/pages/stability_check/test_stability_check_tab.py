from __future__ import annotations

import zipfile

from GAVEL.bootstrap import build_dataset_readers
from GAVEL.core.active_assignment import AssignmentPick
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
    assert tab.results_view.verdict_badge.text() == "STABLE"
    assert tab.results_view.saved_label.text().startswith("Saved to ")
    # Set up collapses to its summary line until Change is pressed.
    assert not tab._form_widget.isVisibleTo(tab)
    assert tab.change_button.isVisibleTo(tab)
    assert tab._set_up_card.subtitle.startswith("Module 9 · folder_grader")

    tab.change_button.click()

    assert vm.state.phase is Phase.SET_UP
    assert tab._form_widget.isVisibleTo(tab)
    assert tab._results_card.isVisibleTo(tab)
    assert tab.run_button.isEnabled()
    # The check just run is in the history, marked as the one on screen.
    assert tab._previous_widget.isVisibleTo(tab)
    assert tab.previous_table.rowCount() == 1
    assert tab.previous_table.item(0, 1).text() == "2"
    assert tab.previous_table.item(0, 2).text() == "Stable"
    shown = tab.previous_table.cellWidget(0, 3)
    assert shown.text() == "Shown"
    assert not shown.isEnabled()
    # The button column is wide enough for the button and a margin, not clipped.
    assert tab.previous_table.columnWidth(3) >= shown.sizeHint().width() + 8

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

    assert tab.results_view.verdict_badge.text() == "UNSTABLE"
    group = tab.results_view.tree.topLevelItem(0)
    assert group.text(0).startswith("Changed · 1 test")
    assert group.child(0).text(0) == "Adds"
    assert group.child(0).text(2) == "1 of 3"

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


def test_open_submission_folder_resolves_the_path(qapp, theme, workspace, course):
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
    opened = []
    tab.open_folder = opened.append

    tab.results_view.open_folder_requested.emit("anon_4821")

    assert opened == [vm.state.module.submission_dirs[1]]
    assert opened[0].name == "anon_4821"

    tab.results_view.open_folder_requested.emit("anon_9999")

    assert len(opened) == 1
    assert tab.status_label.text().startswith("The folder for anon_9999")

    tab.deleteLater()


def _flaky(name, index):
    # The fake counts runs per submission across checks, so flip every other run.
    if name == "anon_4821" and index % 2 == 1:
        return completed({"Adds": (0.0, 2.0)})
    return completed({"Adds": (2.0, 2.0)})


def test_the_history_hides_until_an_autograder_is_picked(qapp, theme, workspace, course):
    tab, vm = _tab(theme, workspace)
    tab.set_course(course)
    tab.assignment_combo.setCurrentIndex(2)
    assert not tab._previous_widget.isVisibleTo(tab)

    _pick_autograder(tab, "folder_grader")

    assert tab._previous_widget.isVisibleTo(tab)
    assert tab.previous_label.text() == "Never checked with folder_grader."
    assert not tab.previous_table.isVisibleTo(tab)

    tab.deleteLater()


def test_a_previous_check_opens_into_the_results(qapp, theme, workspace, course):
    tab, vm = _tab(theme, workspace, FakeAutograderRunner(_flaky))
    tab.set_course(course)
    tab.assignment_combo.setCurrentIndex(2)
    _pick_autograder(tab, "folder_grader")
    tab.runs_spin.setValue(2)
    tab.run_button.click()
    first = vm.state.saved_to
    tab.change_button.click()
    tab.runs_spin.setValue(3)
    tab.run_button.click()
    second = vm.state.saved_to
    assert first != second
    tab.change_button.click()

    table = tab.previous_table
    assert table.rowCount() == 2
    by_runs = {table.item(row, 1).text(): row for row in range(2)}
    assert set(by_runs) == {"2", "3"}
    assert [table.item(row, 2).text() for row in range(2)] == ["1 test changed"] * 2
    assert table.cellWidget(by_runs["3"], 3).text() == "Shown"
    assert table.cellWidget(by_runs["2"], 3).text() == "Open"

    table.cellWidget(by_runs["2"], 3).click()

    assert vm.state.phase is Phase.DONE
    assert vm.state.saved_to == first
    assert tab._results_card.isVisibleTo(tab)
    assert tab.results_view.report is vm.state.report
    assert tab.results_view.report.runs_completed == 2
    assert tab.results_view.saved_label.text() == f"Saved to {first}"
    # Both checks stay listed.
    assert len(vm.state.previous) == 2

    tab.deleteLater()


def test_delete_asks_first_and_removes_the_check(qapp, theme, workspace, course):
    tab, vm = _tab(theme, workspace, FakeAutograderRunner(_flaky))
    tab.set_course(course)
    tab.assignment_combo.setCurrentIndex(2)
    _pick_autograder(tab, "folder_grader")
    tab.runs_spin.setValue(2)
    tab.run_button.click()
    first = vm.state.saved_to
    tab.change_button.click()
    tab.runs_spin.setValue(3)
    tab.run_button.click()
    second = vm.state.saved_to
    tab.change_button.click()
    table = tab.previous_table
    by_runs = {table.item(row, 1).text(): row for row in range(2)}
    asked = []
    tab.confirm = lambda title, text: asked.append((title, text)) or False

    # The check on screen cannot be deleted; the other one asks first.
    assert not table.cellWidget(by_runs["3"], 4).isEnabled()
    assert table.cellWidget(by_runs["3"], 4).toolTip().startswith("This check is on screen")
    table.cellWidget(by_runs["2"], 4).click()

    started = next(p.started_at for p in vm.state.previous if p.path == first)
    assert asked == [
        (
            "Delete this check?",
            f"Delete the check started {started.replace('T', ' ')[:16]}?\n\n"
            "Its saved report is removed from the workspace. This cannot be undone.",
        )
    ]
    assert first.exists()
    assert table.rowCount() == 2

    tab.confirm = lambda title, text: True
    table.cellWidget(by_runs["2"], 4).click()

    assert not first.exists()
    assert second.exists()
    assert table.rowCount() == 1
    assert table.cellWidget(0, 3).text() == "Shown"
    assert vm.state.report is not None and vm.state.saved_to == second

    tab.deleteLater()


def test_run_again_starts_a_new_check_and_keeps_the_earlier_one(qapp, theme, workspace, course):
    tab, vm = _tab(theme, workspace)
    tab.set_course(course)
    tab.assignment_combo.setCurrentIndex(2)
    _pick_autograder(tab, "folder_grader")
    tab.runs_spin.setValue(2)
    tab.run_button.click()
    first = vm.state.saved_to
    assert tab.run_again_button.isEnabled()

    tab.run_again_button.click()

    assert vm.state.phase is Phase.DONE
    assert vm.state.saved_to != first
    assert vm.state.report is not None and vm.state.report.runs_completed == 2
    assert len(vm.state.previous) == 2
    assert first is not None and first.exists()

    tab.set_course(None)

    assert not tab.run_again_button.isEnabled()
    assert tab.run_again_button.toolTip() == "Choose a course"

    tab.deleteLater()


def test_view_in_inspect_grades_names_the_assignment_and_student(qapp, theme, workspace, course):
    tab, vm = _tab(theme, workspace, FakeAutograderRunner(_flaky))
    tab.set_course(course)
    tab.assignment_combo.setCurrentIndex(2)
    _pick_autograder(tab, "folder_grader")
    tab.runs_spin.setValue(2)
    picks = []
    tab.inspect_requested.connect(picks.append)

    tab.results_view.inspect_requested.emit("anon_4821")  # nothing to hand off before a check
    tab.run_button.click()
    tab.results_view.inspect_requested.emit("anon_4821")

    assert picks == [AssignmentPick(course.key.folder_name, 9, "anon_4821")]

    tab.deleteLater()
