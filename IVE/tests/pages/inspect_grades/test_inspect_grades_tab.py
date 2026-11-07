from pathlib import Path

from GAVEL.app.dtos.rubric_definition import (
    RubricCriterionDefinition,
    RubricDefinition,
)
from GAVEL.app.workspace.layout import Workspace
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.inspect_grades.tabs import InspectGradesTab
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel

TEST_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "workspace"
[COURSE] = Workspace(TEST_WORKSPACE).list_courses()


def _tab(theme) -> tuple[InspectGradesTab, InspectGradesViewModel]:
    vm = InspectGradesViewModel(dataset_readers=build_dataset_readers())
    return InspectGradesTab(theme, vm), vm


def test_tab_waits_for_a_course(qapp, theme):
    tab, vm = _tab(theme)

    assert vm.selected_course is None
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
    assert len(vm.human_grades) == 2
    assert len(vm.proxy_grades) == 2
    assert tab.status_label.text() == ("Human grades: 2 assessments\nProxy grades: 2 submissions")
    assert tab.student_grade_matrix.table.rowCount() == 2
    assert tab.student_grade_matrix.table.columnCount() == 6

    assert tab.student_grade_matrix.table.item(0, 0).text() == "100001"
    assert tab.student_grade_matrix.table.item(0, 1).text() == "6"
    assert tab.student_grade_matrix.table.item(0, 4).text() == "4"
    assert tab.student_grade_matrix.table.item(0, 5).text() == "2"

    assert tab.student_grade_matrix.table.item(1, 0).text() == "100002"
    assert tab.student_grade_matrix.table.item(1, 1).text() == "4"
    tab.deleteLater()


def test_clearing_course_resets_assignment_dropdown(qapp, theme):
    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(1)

    tab.set_course(None)

    assert vm.selected_course is None
    assert vm.selected_assignment is None
    assert vm.human_grades == ()
    assert vm.proxy_grades == ()
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
    assert len(vm.human_grades) == 2
    assert len(vm.proxy_grades) == 2

    tab.deleteLater()


def test_selecting_assignment_populates_student_matrix(qapp, theme, monkeypatch):
    rubric = RubricDefinition(
        rubric_id="test_rubric",
        title="Test Rubric",
        points_possible=4.0,
        free_form_criterion_comments=False,
        criteria=(
            RubricCriterionDefinition(
                id="test_criterion",
                description="Test Criterion",
                long_description="",
                points=4.0,
                ratings=(),
            ),
        ),
    )

    monkeypatch.setattr(
        "GAVEL.app.workspace.dataset.CourseDataset.rubric_definition",
        lambda self, assignment_id: rubric,
    )

    tab, vm = _tab(theme)
    tab.set_course(COURSE)

    tab.assignment_combo.setCurrentIndex(2)

    assert vm.rubric_definition == rubric
    assert tab.student_grade_matrix.table.rowCount() == 2
    assert tab.student_grade_matrix.table.columnCount() == 5
    assert tab.student_grade_matrix.table.horizontalHeaderItem(4).text() == "C1"

    tab.assignment_combo.setCurrentIndex(0)

    assert tab.student_grade_matrix.table.rowCount() == 0
    assert tab.student_grade_matrix.table.columnCount() == 0

    tab.deleteLater()
