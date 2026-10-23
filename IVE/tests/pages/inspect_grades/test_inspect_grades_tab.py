from pathlib import Path

from GAVEL.pages.inspect_grades.tabs import InspectGradesTab
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel

TEST_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "workspace"


def test_course_dropdown_loads_available_courses(qapp, theme):
    vm = InspectGradesViewModel(TEST_WORKSPACE, dataset_readers=None)
    tab = InspectGradesTab(theme, vm)

    assert tab.course_combo.count() == 2
    assert tab.course_combo.itemText(0) == "Select a course"
    assert tab.course_combo.itemText(1) == "ser222_25sc_12345"

    tab.deleteLater()


def test_selecting_course_populates_assignments(qapp, theme):
    vm = InspectGradesViewModel(TEST_WORKSPACE, dataset_readers=None)
    tab = InspectGradesTab(theme, vm)

    tab.course_combo.setCurrentIndex(1)

    assert vm.selected_course == vm.courses[0]
    assert tab.assignment_combo.isEnabled()
    assert tab.assignment_combo.count() == 3
    assert tab.assignment_combo.itemText(1) == "Module 3: Programming (Gradescope)"
    assert tab.assignment_combo.itemText(2) == "Module 4: ADJ Problem Set"

    tab.deleteLater()


def test_selecting_assignment_updates_viewmodel(qapp, theme):
    vm = InspectGradesViewModel(TEST_WORKSPACE, dataset_readers=None)
    tab = InspectGradesTab(theme, vm)

    tab.course_combo.setCurrentIndex(1)
    tab.assignment_combo.setCurrentIndex(2)

    assert vm.selected_assignment == vm.assignments[1]

    tab.deleteLater()


def test_clearing_course_resets_assignment_dropdown(qapp, theme):
    vm = InspectGradesViewModel(TEST_WORKSPACE, dataset_readers=None)
    tab = InspectGradesTab(theme, vm)

    tab.course_combo.setCurrentIndex(1)
    tab.assignment_combo.setCurrentIndex(1)
    tab.course_combo.setCurrentIndex(0)

    assert vm.selected_course is None
    assert vm.selected_assignment is None
    assert tab.assignment_combo.count() == 1
    assert not tab.assignment_combo.isEnabled()
    assert tab.status_label.text() == "Select a course to view assignments."

    tab.deleteLater()


def test_refresh_preserves_course_and_assignment(qapp, theme):
    vm = InspectGradesViewModel(TEST_WORKSPACE, dataset_readers=None)
    tab = InspectGradesTab(theme, vm)

    tab.course_combo.setCurrentIndex(1)
    tab.assignment_combo.setCurrentIndex(2)

    selected_course = vm.selected_course
    selected_assignment = vm.selected_assignment

    tab.refresh_button.click()

    assert vm.selected_course == selected_course
    assert vm.selected_assignment == selected_assignment
    assert tab.course_combo.currentIndex() == 1
    assert tab.assignment_combo.currentIndex() == 2

    tab.deleteLater()
