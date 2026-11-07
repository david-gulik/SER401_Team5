from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
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

def test_selecting_student_updates_grade_comparison(qapp, theme):
    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    tab.student_grade_matrix.table.selectRow(0)

    assert tab.selected_student_label.text() == "Selected student: 100001"
    assert tab.human_panel.total_label.text() == "Total: 6 / 6"

    first_row = tab.human_panel.criteria_layout.itemAt(0).widget()
    second_row = tab.human_panel.criteria_layout.itemAt(1).widget()

    assert first_row.layout().itemAt(1).widget().text() == "4 / 4"
    assert second_row.layout().itemAt(1).widget().text() == "2 / 2"

    tab.student_grade_matrix.table.selectRow(1)

    assert tab.selected_student_label.text() == "Selected student: 100002"
    assert tab.human_panel.total_label.text() == "Total: 4 / 6"

    first_row = tab.human_panel.criteria_layout.itemAt(0).widget()
    second_row = tab.human_panel.criteria_layout.itemAt(1).widget()

    assert first_row.layout().itemAt(1).widget().text() == "3 / 4"
    assert second_row.layout().itemAt(1).widget().text() == "1 / 2"

    proxy_first = tab.proxy_panel.criteria_layout.itemAt(0).widget()
    proxy_second = tab.proxy_panel.criteria_layout.itemAt(1).widget()

    assert proxy_first.layout().itemAt(1).widget().text() == "—"
    assert proxy_second.layout().itemAt(1).widget().text() == "—"

    tab.deleteLater()


def test_clearing_student_selection_resets_comparison_panels(qapp, theme):
    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    tab.student_grade_matrix.table.selectRow(0)

    assert tab.human_panel.criteria_layout.count() == 2
    assert tab.proxy_panel.criteria_layout.count() == 2

    tab.student_grade_matrix.table.clearSelection()

    assert tab.human_panel.criteria_layout.count() == 0
    assert tab.proxy_panel.criteria_layout.count() == 0

    assert tab.human_panel.total_label.text() == "Total: —"
    assert tab.proxy_panel.total_label.text() == "Total: —"

    assert (
        tab.selected_student_label.text()
        == "Select a student from the matrix to view grading details."
    )

    tab.deleteLater()


def test_grade_comparison_panels_scroll_together(qapp, theme):
    tab, vm = _tab(theme)

    criteria = tuple(
        RubricCriterionDefinition(
            id=f"criterion_{i}",
            description=f"Criterion {i}",
            long_description="",
            points=4.0,
            ratings=(),
        )
        for i in range(20)
    )

    rubric = RubricDefinition(
        rubric_id="scroll_test",
        title="Scrolling Test",
        points_possible=80.0,
        free_form_criterion_comments=False,
        criteria=criteria,
    )

    tab.resize(1100, 700)
    tab.show()

    scores = {criterion.id: 4.0 for criterion in criteria}

    tab.human_panel.display_criteria(rubric, scores)
    tab.proxy_panel.display_criteria(rubric, None)

    qapp.processEvents()

    human_scrollbar = tab.human_panel.scroll_area.verticalScrollBar()
    proxy_scrollbar = tab.proxy_panel.scroll_area.verticalScrollBar()

    assert tab.human_panel.criteria_layout.count() == 20
    assert tab.proxy_panel.criteria_layout.count() == 20

    assert human_scrollbar.maximum() > 0
    assert proxy_scrollbar.maximum() > 0

    human_scrollbar.setValue(200)
    assert proxy_scrollbar.value() == human_scrollbar.value()

    proxy_scrollbar.setValue(400)
    assert human_scrollbar.value() == proxy_scrollbar.value()

    human_scrollbar.setValue(0)
    assert proxy_scrollbar.value() == 0

    human_scrollbar.setValue(200)
    assert human_scrollbar.value() > 0
    assert proxy_scrollbar.value() == human_scrollbar.value()

    tab.human_panel.display_criteria(rubric, scores)
    tab.proxy_panel.display_criteria(rubric, None)

    qapp.processEvents()

    assert human_scrollbar.value() == 0
    assert proxy_scrollbar.value() == 0

    tab.close()
    tab.deleteLater()


def test_switching_students_resets_comparison_scroll(qapp, theme):
    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    tab.student_grade_matrix.table.selectRow(0)

    human_scrollbar = tab.human_panel.scroll_area.verticalScrollBar()
    proxy_scrollbar = tab.proxy_panel.scroll_area.verticalScrollBar()

    human_scrollbar.setValue(100)

    tab.student_grade_matrix.table.selectRow(1)

    assert human_scrollbar.value() == 0
    assert proxy_scrollbar.value() == 0

    assert tab.selected_student_label.text() == "Selected student: 100002"
    assert tab.human_panel.total_label.text() == "Total: 4 / 6"

    tab.deleteLater()


def test_criterion_selection_is_synchronized(qapp, theme):
    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)
    tab.student_grade_matrix.table.selectRow(1)

    tab.resize(1100, 900)
    tab.show()
    qapp.processEvents()

    human_c1 = tab.human_panel.criteria_layout.itemAt(0).widget()
    human_c2 = tab.human_panel.criteria_layout.itemAt(1).widget()

    proxy_c1 = tab.proxy_panel.criteria_layout.itemAt(0).widget()
    proxy_c2 = tab.proxy_panel.criteria_layout.itemAt(1).widget()

    QTest.mouseClick(human_c1, Qt.MouseButton.LeftButton)

    assert human_c1.property("selected") == "true"
    assert proxy_c1.property("selected") == "true"
    assert human_c2.property("selected") == "false"
    assert proxy_c2.property("selected") == "false"

    QTest.mouseClick(proxy_c2, Qt.MouseButton.LeftButton)

    assert human_c1.property("selected") == "false"
    assert proxy_c1.property("selected") == "false"
    assert human_c2.property("selected") == "true"
    assert proxy_c2.property("selected") == "true"

    tab.student_grade_matrix.table.selectRow(0)

    for panel in (tab.human_panel, tab.proxy_panel):
        for index in range(panel.criteria_layout.count()):
            card = panel.criteria_layout.itemAt(index).widget()
            assert card.property("selected") == "false"

    tab.close()
    tab.deleteLater()
