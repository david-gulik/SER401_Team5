from pathlib import Path

from GAVEL.app.workspace.layout import Workspace
from GAVEL.pages.inspect_grades.tabs import InspectGradesTab
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel

TEST_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "workspace"
[COURSE] = Workspace(TEST_WORKSPACE).list_courses()


def _tab(theme) -> tuple[InspectGradesTab, InspectGradesViewModel]:
    vm = InspectGradesViewModel(dataset_readers=None)
    return InspectGradesTab(theme, vm), vm


def test_tab_waits_for_a_course(qapp, theme):
    tab, vm = _tab(theme)

    assert tab.assignment_combo.count() == 1
    assert tab.assignment_combo.itemText(0) == "Select an assignment"
    assert not tab.assignment_combo.isEnabled()
    assert tab.status_label.text() == "Choose a course to view its assignments."

    tab.deleteLater()


def test_set_course_populates_assignments(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)

    assert vm.selected_course == COURSE
    assert tab.assignment_combo.isEnabled()
    assert tab.assignment_combo.count() == 3
    assert tab.assignment_combo.itemText(1) == "Module 3: Programming (Gradescope)"
    assert tab.assignment_combo.itemText(2) == "Module 4: ADJ Problem Set"
    assert tab.status_label.text() == "Select an assignment."

    tab.deleteLater()


def test_selecting_assignment_updates_viewmodel(qapp, theme):
    tab, vm = _tab(theme)
    tab.set_course(COURSE)

    tab.assignment_combo.setCurrentIndex(2)

    assert vm.selected_assignment == vm.assignments[1]

    tab.deleteLater()


def test_clearing_course_resets_assignment_dropdown(qapp, theme):
    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(1)

    tab.set_course(None)

    assert vm.selected_course is None
    assert vm.selected_assignment is None
    assert tab.assignment_combo.count() == 1
    assert not tab.assignment_combo.isEnabled()
    assert tab.status_label.text() == "Choose a course to view its assignments."

    tab.deleteLater()


def test_refresh_preserves_the_assignment(qapp, theme):
    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)
    selected_assignment = vm.selected_assignment

    tab.refresh_button.click()

    assert vm.selected_course == COURSE
    assert vm.selected_assignment == selected_assignment
    assert tab.assignment_combo.currentIndex() == 2

    tab.deleteLater()
