from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from GAVEL.app.dtos.rubric_definition import (
    RubricCriterionDefinition,
    RubricDefinition,
)
from GAVEL.app.workspace.layout import Workspace
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.inspect_grades.correction_store import load_corrections
from GAVEL.pages.inspect_grades.tabs import InspectGradesTab
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel

TEST_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "workspace"
[COURSE] = Workspace(TEST_WORKSPACE).list_courses()


@pytest.fixture(autouse=True)
def isolate_correction_files(tmp_path, monkeypatch):
    correction_file = tmp_path / "corrections.json"

    monkeypatch.setattr(
        InspectGradesViewModel,
        "_corrections_path",
        lambda self: correction_file if self.selected_assignment is not None else None,
    )


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

    assert tab.status_label.text() == (
        "Human grades: 2 assessments\n"
        "Proxy grades: 2 submissions\n"
        "Proxy scores unavailable: No proxy-grade mapping "
        "is registered for this course and module."
    )

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


def test_autograder_zip_dropdown_selection(qapp, theme, tmp_path, monkeypatch):
    autograder_dir = tmp_path / "autograders" / "ser222"
    autograder_dir.mkdir(parents=True)

    first_zip = autograder_dir / "autograder_v1.zip"
    second_zip = autograder_dir / "autograder_v2.zip"

    first_zip.touch()
    second_zip.touch()

    monkeypatch.setattr(
        Workspace,
        "course_autograders_dir",
        lambda self, key: autograder_dir,
    )

    tab, vm = _tab(theme)

    assert not tab.autograder_zip_combo.isEnabled()

    tab.set_course(COURSE)

    assert tab.autograder_zip_combo.count() == 3
    assert not tab.autograder_zip_combo.isEnabled()

    tab.assignment_combo.setCurrentIndex(2)

    assert tab.autograder_zip_combo.isEnabled()

    tab.autograder_zip_combo.setCurrentIndex(1)

    assert vm.selected_autograder_zip == first_zip

    tab.assignment_combo.setCurrentIndex(1)

    assert vm.selected_autograder_zip is None
    assert tab.autograder_zip_combo.currentIndex() == 0
    assert tab.autograder_zip_combo.isEnabled()

    tab.autograder_zip_combo.setCurrentIndex(2)

    assert vm.selected_autograder_zip == second_zip

    tab.set_course(None)

    assert vm.selected_autograder_zip is None
    assert vm.available_autograder_zips == ()
    assert not tab.autograder_zip_combo.isEnabled()

    tab.deleteLater()


def test_autograder_zip_dropdown_handles_no_files(qapp, theme, tmp_path, monkeypatch):
    monkeypatch.setattr(
        Workspace,
        "course_autograders_dir",
        lambda self, key: tmp_path / "autograders" / "ser222",
    )

    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    assert vm.available_autograder_zips == ()
    assert vm.selected_autograder_zip is None

    assert tab.autograder_zip_combo.count() == 1
    assert tab.autograder_zip_combo.currentText() == "No autograder ZIPs available"
    assert not tab.autograder_zip_combo.isEnabled()

    assert len(vm.human_grades) == 2
    assert len(vm.proxy_grades) == 2

    tab.deleteLater()


def test_refresh_resets_autograder_zip_selection(qapp, theme, tmp_path, monkeypatch):
    autograder_dir = tmp_path / "autograders" / "ser222"
    autograder_dir.mkdir(parents=True)

    zip_path = autograder_dir / "autograder_v1.zip"
    zip_path.touch()

    monkeypatch.setattr(
        Workspace,
        "course_autograders_dir",
        lambda self, key: autograder_dir,
    )

    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    tab.autograder_zip_combo.setCurrentIndex(1)

    assert vm.selected_autograder_zip == zip_path

    tab.refresh_button.click()

    assert vm.selected_assignment == vm.assignments[1]
    assert vm.selected_autograder_zip is None
    assert tab.autograder_zip_combo.currentIndex() == 0
    assert tab.autograder_zip_combo.isEnabled()

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


def test_criterion_selection_updates_rubric_correction_panel(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    tab.student_grade_matrix.table.selectRow(0)

    rubric = vm.rubric_definition
    assert rubric is not None

    tab.human_panel.criterion_selected.emit(0)

    correction_panel = tab.rubric_correction_panel

    assert correction_panel.student_label.text() == "Student: 100001"
    assert correction_panel.criterion_label.text() == (
        f"Criterion: {rubric.criteria[0].description}"
    )
    assert correction_panel.original_grade_label.text() == (
        f"Original Grade (Canvas): 4 / {rubric.criteria[0].points:g}"
    )

    assert tab.human_panel.criteria_layout.itemAt(0).widget().property("selected") == "true"
    assert tab.proxy_panel.criteria_layout.itemAt(0).widget().property("selected") == "true"

    tab.student_grade_matrix.table.selectRow(1)

    assert correction_panel.student_label.text() == "Student: —"
    assert correction_panel.grade_buttons.buttons() == []

    tab.deleteLater()


def test_corrected_grade_is_stored_in_viewmodel(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    tab.student_grade_matrix.table.selectRow(1)

    tab.human_panel.criterion_selected.emit(1)

    assert vm.get_correction(100002, "crit_2") is None

    buttons = tab.rubric_correction_panel.grade_buttons.buttons()

    assert len(buttons) == 3
    assert buttons[1].isChecked()

    buttons[0].click()

    assert vm.get_correction(100002, "crit_2") == 2.0

    assert vm.get_correction(100002, "crit_1") is None
    assert vm.get_correction(100001, "crit_2") is None

    assessment = next(a for a in vm.human_grades if a.student_id == 100002)

    original_score = next(
        score.points for score in assessment.criteria if score.criterion_id == "crit_2"
    )

    assert original_score == 1.0

    tab.deleteLater()


def test_correction_updates_human_panel_and_total(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)
    tab.student_grade_matrix.table.selectRow(1)

    tab.human_panel.criterion_selected.emit(1)

    assert tab.human_panel.total_label.text() == "Total: 4 / 6"

    buttons = tab.rubric_correction_panel.grade_buttons.buttons()
    buttons[0].click()

    assert vm.get_correction(100002, "crit_2") == 2.0

    assert tab.human_panel.total_label.text() == ("Total: 5 / 6 (corrected)")

    corrected_card = tab.human_panel.criteria_layout.itemAt(1).widget()

    assert corrected_card.layout().itemAt(1).widget().text() == "2 / 2"
    assert corrected_card.property("selected") == "true"

    assessment = next(a for a in vm.human_grades if a.student_id == 100002)

    original_score = next(
        score.points for score in assessment.criteria if score.criterion_id == "crit_2"
    )

    assert original_score == 1.0

    tab.deleteLater()


def test_reselecting_criterion_restores_correction(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)
    tab.student_grade_matrix.table.selectRow(1)

    tab.human_panel.criterion_selected.emit(1)
    tab.rubric_correction_panel.grade_buttons.buttons()[0].click()

    assert vm.get_correction(100002, "crit_2") == 2.0

    tab.human_panel.criterion_selected.emit(0)
    tab.human_panel.criterion_selected.emit(1)

    buttons = tab.rubric_correction_panel.grade_buttons.buttons()

    assert buttons[0].isChecked()
    assert not buttons[1].isChecked()

    assert tab.rubric_correction_panel.original_grade_label.text() == (
        "Original Grade (Canvas): 1 / 2"
    )

    assert tab.human_panel.total_label.text() == ("Total: 5 / 6 (corrected)")

    tab.deleteLater()


def test_switching_students_preserves_corrected_grades(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    tab.student_grade_matrix.table.selectRow(1)
    tab.human_panel.criterion_selected.emit(1)
    tab.rubric_correction_panel.grade_buttons.buttons()[0].click()

    assert vm.get_correction(100002, "crit_2") == 2.0
    assert tab.human_panel.total_label.text() == ("Total: 5 / 6 (corrected)")

    tab.student_grade_matrix.table.selectRow(0)

    assert tab.human_panel.total_label.text() == "Total: 6 / 6"
    assert vm.get_correction(100001, "crit_2") is None

    tab.student_grade_matrix.table.selectRow(1)

    assert tab.human_panel.total_label.text() == ("Total: 5 / 6 (corrected)")

    corrected_card = tab.human_panel.criteria_layout.itemAt(1).widget()

    assert corrected_card.layout().itemAt(1).widget().text() == "2 / 2"

    tab.human_panel.criterion_selected.emit(1)

    buttons = tab.rubric_correction_panel.grade_buttons.buttons()

    assert buttons[0].isChecked()
    assert tab.rubric_correction_panel.original_grade_label.text() == (
        "Original Grade (Canvas): 1 / 2"
    )

    tab.deleteLater()


def test_correction_updates_matrix_and_human_panel(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)
    tab.student_grade_matrix.table.selectRow(1)

    matrix = tab.student_grade_matrix.table

    assert matrix.item(1, 1).text() == "4"
    assert matrix.item(1, 5).text() == "1"

    tab.human_panel.criterion_selected.emit(1)
    tab.rubric_correction_panel.grade_buttons.buttons()[0].click()

    assert vm.get_correction(100002, "crit_2") == 2.0

    assert matrix.item(1, 1).text() == "5*"
    assert matrix.item(1, 5).text() == "2*"

    assert tab.human_panel.total_label.text() == ("Total: 5 / 6 (corrected)")

    assert matrix.currentRow() == 1
    assert tab.selected_student_label.text() == ("Selected student: 100002")

    assessment = next(a for a in vm.human_grades if a.student_id == 100002)

    original_score = next(
        score.points for score in assessment.criteria if score.criterion_id == "crit_2"
    )

    assert original_score == 1.0
    tab.rubric_correction_panel.grade_buttons.buttons()[1].click()

    assert vm.get_correction(100002, "crit_2") is None
    tab.deleteLater()


def test_changing_grade_automatically_saves_correction(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)
    tab.student_grade_matrix.table.selectRow(1)
    tab.human_panel.criterion_selected.emit(1)

    tab.rubric_correction_panel.grade_buttons.buttons()[0].click()

    path = vm._corrections_path()
    assert path is not None
    assert path.is_file()

    saved_corrections, saved_notes = load_corrections(path)

    assert saved_corrections == {(100002, "crit_2"): 2.0}
    assert saved_notes == {}

    tab.rubric_correction_panel.grade_buttons.buttons()[1].click()

    saved_corrections, saved_notes = load_corrections(path)

    assert saved_corrections == {}
    assert saved_notes == {}

    tab.deleteLater()


def test_criterion_notes_are_saved(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)
    tab.student_grade_matrix.table.selectRow(1)
    tab.human_panel.criterion_selected.emit(1)

    tab.rubric_correction_panel.notes_input.setPlainText("Reviewed the student's work.")

    path = vm._corrections_path()
    assert path is not None

    saved_corrections, saved_notes = load_corrections(path)

    assert saved_corrections == {}
    assert saved_notes == {(100002, "crit_2"): "Reviewed the student's work."}

    tab.rubric_correction_panel.notes_input.clear()

    saved_corrections, saved_notes = load_corrections(path)

    assert saved_notes == {}

    tab.deleteLater()


def test_saved_notes_restore_when_reselecting_criterion(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)
    tab.student_grade_matrix.table.selectRow(1)

    tab.human_panel.criterion_selected.emit(1)

    tab.rubric_correction_panel.notes_input.setPlainText("Reviewed the student's work.")

    assert vm.notes[(100002, "crit_2")] == ("Reviewed the student's work.")

    tab.human_panel.criterion_selected.emit(0)

    assert tab.rubric_correction_panel.notes_input.toPlainText() == ""

    tab.human_panel.criterion_selected.emit(1)

    assert tab.rubric_correction_panel.notes_input.toPlainText() == ("Reviewed the student's work.")

    tab.deleteLater()


def test_reopening_assignment_restores_saved_corrections_and_notes(
    qapp, theme, tmp_path, monkeypatch
):
    tab, vm = _tab(theme)

    monkeypatch.setattr(
        vm,
        "_corrections_path",
        lambda: (
            tmp_path / f"{vm.selected_assignment.canvas_id}.json"
            if vm.selected_assignment is not None
            else None
        ),
    )

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)
    tab.student_grade_matrix.table.selectRow(1)
    tab.human_panel.criterion_selected.emit(1)

    tab.rubric_correction_panel.grade_buttons.buttons()[0].click()
    tab.rubric_correction_panel.notes_input.setPlainText("Awarded full credit after review.")

    assert tab.student_grade_matrix.table.item(1, 1).text() == "5*"

    tab.assignment_combo.setCurrentIndex(0)
    tab.assignment_combo.setCurrentIndex(2)

    assert vm.get_correction(100002, "crit_2") == 2.0
    assert vm.notes[(100002, "crit_2")] == ("Awarded full credit after review.")

    matrix = tab.student_grade_matrix.table
    assert matrix.item(1, 1).text() == "5*"
    assert matrix.item(1, 5).text() == "2*"

    matrix.selectRow(1)
    tab.human_panel.criterion_selected.emit(1)

    assert tab.human_panel.total_label.text() == ("Total: 5 / 6 (corrected)")
    assert tab.rubric_correction_panel.grade_buttons.buttons()[0].isChecked()
    assert tab.rubric_correction_panel.notes_input.toPlainText() == (
        "Awarded full credit after review."
    )

    tab.deleteLater()


def test_corrupted_correction_file_displays_warning(qapp, theme, tmp_path, monkeypatch):
    tab, vm = _tab(theme)

    correction_file = tmp_path / "corrections.json"
    correction_file.write_text("{invalid json", encoding="utf-8")

    monkeypatch.setattr(
        vm,
        "_corrections_path",
        lambda: correction_file if vm.selected_assignment is not None else None,
    )

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    assert vm.corrections_error is not None
    assert "WARNING:" in tab.status_label.text()
    assert "correction saving is disabled" in tab.status_label.text()
    assert not tab.rubric_correction_panel.isEnabled()
    assert tab.student_grade_matrix.isEnabled()
    assert tab.human_panel.isEnabled()

    assert tab.student_grade_matrix.table.rowCount() == 2
    assert tab.student_grade_matrix.table.item(1, 1).text() == "4"

    assert correction_file.read_text(encoding="utf-8") == "{invalid json"

    tab.deleteLater()


def test_save_error_displays_warning_and_disables_corrections(qapp, theme, monkeypatch):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)
    tab.student_grade_matrix.table.selectRow(1)
    tab.human_panel.criterion_selected.emit(1)

    def fail_save(path, corrections, notes):
        raise PermissionError("Access denied")

    monkeypatch.setattr(
        "GAVEL.pages.inspect_grades.viewmodel.save_corrections",
        fail_save,
    )

    tab.rubric_correction_panel.grade_buttons.buttons()[0].click()

    assert vm.corrections_error is not None
    assert "Could not save rubric corrections" in vm.corrections_error

    assert "WARNING:" in tab.status_label.text()
    assert "could not be saved" in tab.status_label.text()
    assert "Access denied" in tab.status_label.text()

    assert not tab.rubric_correction_panel.isEnabled()
    assert tab.student_grade_matrix.isEnabled()
    assert tab.human_panel.isEnabled()

    assert vm.get_correction(100002, "crit_2") == 2.0

    tab.deleteLater()


def test_correction_error_resets_when_switching_assignments(qapp, theme, monkeypatch):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    vm.corrections_error = "Could not save rubric corrections: Access denied"
    tab._render_grading_status()
    tab.rubric_correction_panel.setEnabled(False)

    assert not tab.rubric_correction_panel.isEnabled()

    tab.assignment_combo.setCurrentIndex(0)

    assert vm.corrections_error is None
    assert tab.rubric_correction_panel.isEnabled()
    assert "WARNING:" not in tab.status_label.text()

    tab.deleteLater()


def test_calculated_proxy_scores_populate_student_matrix(qapp, theme, monkeypatch):
    monkeypatch.setattr(
        InspectGradesViewModel,
        "resolve_mapping_name",
        lambda self: "test_mapping",
    )

    monkeypatch.setattr(
        InspectGradesViewModel,
        "calculated_proxy_scores",
        lambda self: {
            100002: {
                "crit_1": 3.0,
                "crit_2": 2.0,
            },
        },
    )

    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    matrix = tab.student_grade_matrix.table

    assert tab._proxy_scores_by_student == {
        100002: {
            "crit_1": 3.0,
            "crit_2": 2.0,
        },
    }

    assert matrix.item(0, 2).text() == "—"
    assert matrix.item(0, 3).text() == "—"

    assert matrix.item(1, 1).text() == "4"
    assert matrix.item(1, 2).text() == "5"
    assert matrix.item(1, 3).text() == "-1"

    assert matrix.item(1, 4).text() == "3/3"
    assert matrix.item(1, 5).text() == "1/2"

    legend = tab.student_grade_matrix.legend_label.text()
    assert "Match: 1" in legend
    assert "Mismatch: 1" in legend

    tab.deleteLater()


def test_selected_student_displays_calculated_proxy_grades(qapp, theme, monkeypatch):
    monkeypatch.setattr(
        InspectGradesViewModel,
        "resolve_mapping_name",
        lambda self: "test_mapping",
    )

    monkeypatch.setattr(
        InspectGradesViewModel,
        "calculated_proxy_scores",
        lambda self: {
            100002: {
                "crit_1": 3.0,
                "crit_2": 2.0,
            },
        },
    )

    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    tab.student_grade_matrix.table.selectRow(1)

    assert tab.proxy_panel.total_label.text() == "Total: 5 / 6"
    assert tab.proxy_panel.criteria_layout.count() == 2

    first_criterion = tab.proxy_panel.criteria_layout.itemAt(0).widget()
    second_criterion = tab.proxy_panel.criteria_layout.itemAt(1).widget()

    assert first_criterion.layout().itemAt(1).widget().text() == "3 / 4"
    assert second_criterion.layout().itemAt(1).widget().text() == "2 / 2"

    tab.student_grade_matrix.table.selectRow(0)

    assert tab.proxy_panel.total_label.text() == ("Total: — (proxy grades unavailable)")

    tab.deleteLater()


def test_rubric_correction_updates_proxy_comparison(qapp, theme, monkeypatch):
    monkeypatch.setattr(
        InspectGradesViewModel,
        "resolve_mapping_name",
        lambda self: "test_mapping",
    )

    monkeypatch.setattr(
        InspectGradesViewModel,
        "calculated_proxy_scores",
        lambda self: {
            100002: {
                "crit_1": 3.0,
                "crit_2": 2.0,
            },
        },
    )

    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    matrix = tab.student_grade_matrix.table
    matrix.selectRow(1)

    assert matrix.item(1, 1).text() == "4"
    assert matrix.item(1, 2).text() == "5"
    assert matrix.item(1, 3).text() == "-1"
    assert matrix.item(1, 5).text() == "1/2"

    tab.human_panel.criterion_selected.emit(1)
    tab.rubric_correction_panel.grade_buttons.buttons()[0].click()

    assert matrix.item(1, 1).text() == "5*"
    assert matrix.item(1, 2).text() == "5"
    assert matrix.item(1, 3).text() == "0"
    assert matrix.item(1, 5).text() == "2*/2"

    assert tab.human_panel.total_label.text() == ("Total: 5 / 6 (corrected)")

    assert tab.proxy_panel.total_label.text() == "Total: 5 / 6"
    assert tab._proxy_scores_by_student[100002] == {
        "crit_1": 3.0,
        "crit_2": 2.0,
    }

    tab.rubric_correction_panel.grade_buttons.buttons()[1].click()

    assert vm.get_correction(100002, "crit_2") is None
    assert matrix.item(1, 1).text() == "4"
    assert matrix.item(1, 2).text() == "5"
    assert matrix.item(1, 3).text() == "-1"
    assert matrix.item(1, 5).text() == "1/2"

    tab.deleteLater()


def test_mismatch_filter_updates_after_rubric_correction(qapp, theme, monkeypatch):
    monkeypatch.setattr(
        InspectGradesViewModel,
        "resolve_mapping_name",
        lambda self: "test_mapping",
    )

    monkeypatch.setattr(
        InspectGradesViewModel,
        "calculated_proxy_scores",
        lambda self: {
            100002: {
                "crit_1": 3.0,
                "crit_2": 2.0,
            },
        },
    )

    tab, vm = _tab(theme)
    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    grade_matrix = tab.student_grade_matrix
    matrix = grade_matrix.table

    matrix.selectRow(1)
    tab.human_panel.criterion_selected.emit(1)

    grade_matrix.mismatch_checkbox.setChecked(True)

    assert matrix.isRowHidden(0)
    assert not matrix.isRowHidden(1)

    tab.rubric_correction_panel.grade_buttons.buttons()[0].click()

    assert matrix.isRowHidden(0)
    assert matrix.isRowHidden(1)
    assert not grade_matrix.empty_label.isHidden()

    grade_matrix.mismatch_checkbox.setChecked(False)
    matrix.selectRow(1)
    tab.human_panel.criterion_selected.emit(1)

    tab.rubric_correction_panel.grade_buttons.buttons()[1].click()

    assert matrix.item(1, 5).text() == "1/2"

    grade_matrix.mismatch_checkbox.setChecked(True)

    assert matrix.isRowHidden(0)
    assert not matrix.isRowHidden(1)

    tab.deleteLater()


def test_missing_proxy_mapping_displays_status_message(qapp, theme):
    tab, vm = _tab(theme)

    tab.set_course(COURSE)
    tab.assignment_combo.setCurrentIndex(2)

    assert vm.resolve_mapping_name() is None

    assert "Proxy scores unavailable: No proxy-grade mapping" in tab.status_label.text()

    assert tab.student_grade_matrix.table.rowCount() == 2
    assert tab.student_grade_matrix.table.item(1, 1).text() == "4"

    tab.deleteLater()
