from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.inspect_grades.grade_comparison_panel import GradeComparisonPanel
from GAVEL.pages.inspect_grades.rubric_correction_panel import RubricCorrectionPanel
from GAVEL.pages.inspect_grades.student_grade_matrix import StudentGradeMatrix
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard


class InspectGradesTab(ScrollableTab):
    def __init__(
        self,
        theme: ThemeContext,
        viewmodel: InspectGradesViewModel,
    ) -> None:
        super().__init__(theme)
        self._viewmodel = viewmodel

        card = SectionCard(theme, "Assignment Selection")

        self.assignment_combo = QComboBox()
        self.autograder_zip_combo = QComboBox()
        self.autograder_zip_combo.setEnabled(False)
        self.autograder_zip_combo.setToolTip(
            "Select an available autograder ZIP for the current course."
        )
        self.status_label = QLabel()
        self.status_label.setProperty("role", "text_muted")
        self.status_label.setWordWrap(True)

        self.refresh_button = QPushButton("Refresh Assignments")
        self.refresh_button.clicked.connect(self.refresh)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.addRow("Assignment", self.assignment_combo)
        form.addRow("Autograder ZIP (Proxy Grades)", self.autograder_zip_combo)

        card.add_row(form_widget)
        card.add_row(self.refresh_button)
        card.add_row(self.status_label)

        self.add_section(card)

        self.student_grade_matrix = StudentGradeMatrix(theme)
        self.add_section(self.student_grade_matrix)

        self.selected_student_label = QLabel(
            "Select a student from the matrix to view grading details."
        )
        self.selected_student_label.setProperty("role", "text_muted")
        self.add_section(self.selected_student_label)

        panels_widget = QWidget()
        panels_layout = QHBoxLayout(panels_widget)
        panels_layout.setContentsMargins(0, 0, 0, 0)
        panels_layout.setSpacing(12)

        self.human_panel = GradeComparisonPanel(theme, "Human Grade")
        self.proxy_panel = GradeComparisonPanel(theme, "Proxy / Autograder Grade")
        self.rubric_correction_panel = RubricCorrectionPanel(theme)
        self._selected_criterion_index: int | None = None

        self.rubric_correction_panel.correction_changed.connect(self._on_correction_changed)

        self.rubric_correction_panel.notes_changed.connect(self._on_notes_changed)

        self.human_panel.setMinimumWidth(280)
        self.proxy_panel.setMinimumWidth(280)
        self.rubric_correction_panel.setMinimumWidth(280)

        panels_layout.addWidget(self.human_panel, 1)
        panels_layout.addWidget(self.proxy_panel, 1)
        panels_layout.addWidget(self.rubric_correction_panel, 1)

        self.add_section(panels_widget)

        human_scrollbar = self.human_panel.scroll_area.verticalScrollBar()
        proxy_scrollbar = self.proxy_panel.scroll_area.verticalScrollBar()

        human_scrollbar.valueChanged.connect(proxy_scrollbar.setValue)
        proxy_scrollbar.valueChanged.connect(human_scrollbar.setValue)

        self.human_panel.criterion_selected.connect(self._on_criterion_selected)
        self.proxy_panel.criterion_selected.connect(self._on_criterion_selected)

        self.human_details_label = self.human_panel.message_label
        self.proxy_details_label = self.proxy_panel.message_label

        self.student_grade_matrix.table.itemSelectionChanged.connect(self._on_student_selected)
        self.add_stretch()

        self.assignment_combo.currentIndexChanged.connect(self._on_assignment_changed)
        self.autograder_zip_combo.currentIndexChanged.connect(self._on_autograder_zip_changed)

        self._render_assignments()
        self._render_autograder_zips()

    def set_course(self, course: CourseFolder | None) -> None:
        self._viewmodel.select_course(course)
        self.student_grade_matrix.clear()
        self._on_student_selected()
        self.selected_student_label.setText(
            "Select a student from the matrix to view grading details."
        )
        self._render_assignments()
        self._render_autograder_zips()

    def refresh(self) -> None:
        previous_assignment = self._viewmodel.selected_assignment

        self.set_course(self._viewmodel.selected_course)

        if previous_assignment is None:
            return

        for index in range(1, self.assignment_combo.count()):
            assignment = self.assignment_combo.itemData(index)

            if assignment.canvas_id == previous_assignment.canvas_id:
                self.assignment_combo.setCurrentIndex(index)
                break

    def _render_assignments(self) -> None:
        self.assignment_combo.blockSignals(True)
        self.assignment_combo.clear()
        self.assignment_combo.addItem("Select an assignment", None)

        for assignment in self._viewmodel.assignments:
            self.assignment_combo.addItem(assignment.name, assignment)

        self.assignment_combo.blockSignals(False)
        self.assignment_combo.setEnabled(bool(self._viewmodel.assignments))

        if self._viewmodel.selected_course is None:
            self.status_label.setText("Choose a course to view its assignments.")
        elif self._viewmodel.assignment_error:
            self.status_label.setText(
                f"Could not load assignments: {self._viewmodel.assignment_error}"
            )
        elif not self._viewmodel.assignments:
            self.status_label.setText("No assignments available for this course.")
        else:
            self.status_label.setText("Select an assignment.")

    def _on_assignment_changed(self, index: int) -> None:
        assignment = self.assignment_combo.itemData(index)
        self._viewmodel.select_assignment(assignment)
        self._render_autograder_zips()
        self._render_grading_status()

        self.student_grade_matrix.clear()
        self._on_student_selected()

        if self._viewmodel.rubric_definition is not None:
            rubric = self._viewmodel.rubric_definition

            self.student_grade_matrix.display(
                self._viewmodel.human_grades,
                rubric,
            )

            if self._viewmodel.corrections:
                for assessment in self._viewmodel.human_grades:
                    self.student_grade_matrix.update_corrected_row(
                        assessment,
                        rubric,
                        self._viewmodel.corrections,
                    )

    def _render_autograder_zips(self) -> None:
        self.autograder_zip_combo.blockSignals(True)
        self.autograder_zip_combo.clear()

        if self._viewmodel.autograder_zip_error:
            placeholder = "Could not load autograder ZIPs"
        elif not self._viewmodel.available_autograder_zips:
            placeholder = "No autograder ZIPs available"
        else:
            placeholder = "Select an autograder ZIP"

        self.autograder_zip_combo.addItem(placeholder, None)

        for zip_path in self._viewmodel.available_autograder_zips:
            self.autograder_zip_combo.addItem(zip_path.name, zip_path)

        selected_zip = self._viewmodel.selected_autograder_zip

        if selected_zip is not None:
            index = self.autograder_zip_combo.findData(selected_zip)
            if index >= 0:
                self.autograder_zip_combo.setCurrentIndex(index)

        self.autograder_zip_combo.setEnabled(
            self._viewmodel.selected_assignment is not None
            and bool(self._viewmodel.available_autograder_zips)
            and self._viewmodel.autograder_zip_error is None
        )

        self.autograder_zip_combo.blockSignals(False)

    def _on_autograder_zip_changed(self, index: int) -> None:
        zip_path = self.autograder_zip_combo.itemData(index)
        self._viewmodel.select_autograder_zip(zip_path)

    def _render_grading_status(self) -> None:
        if self._viewmodel.selected_assignment is None:
            self.status_label.setText("Select an assignment.")
            return

        messages = []

        if self._viewmodel.human_grades_error:
            messages.append(f"Human grades: {self._viewmodel.human_grades_error}")
        else:
            messages.append(f"Human grades: {len(self._viewmodel.human_grades)} assessments")

        if self._viewmodel.proxy_grades_error:
            messages.append(f"Proxy grades: {self._viewmodel.proxy_grades_error}")
        else:
            messages.append(f"Proxy grades: {len(self._viewmodel.proxy_grades)} submissions")

        if self._viewmodel.rubric_definition_error:
            messages.append(f"Student matrix: {self._viewmodel.rubric_definition_error}")

        self.status_label.setText("\n".join(messages))

    def _on_criterion_selected(self, index: int) -> None:
        self.human_panel.select_criterion(index)
        self.proxy_panel.select_criterion(index)

        self._selected_criterion_index = None

        selected_rows = self.student_grade_matrix.table.selectionModel().selectedRows()
        rubric = self._viewmodel.rubric_definition

        if not selected_rows or rubric is None:
            self.rubric_correction_panel.clear()
            return

        if not 0 <= index < len(rubric.criteria):
            self.rubric_correction_panel.clear()
            return

        row = selected_rows[0].row()
        student_item = self.student_grade_matrix.table.item(row, 0)

        if student_item is None:
            self.rubric_correction_panel.clear()
            return

        student_id = int(student_item.text())
        criterion = rubric.criteria[index]

        assessment = next(
            (
                assessment
                for assessment in self._viewmodel.human_grades
                if assessment.student_id == student_id
            ),
            None,
        )

        original_score = None

        if assessment is not None:
            original_score = next(
                (
                    score.points
                    for score in assessment.criteria
                    if score.criterion_id == criterion.id
                ),
                None,
            )

        self._selected_criterion_index = index

        self.rubric_correction_panel.set_criterion(
            student_id=student_id,
            criterion=criterion,
            original_score=original_score,
            corrected_score=self._viewmodel.get_correction(
                student_id,
                criterion.id,
            ),
        )

        saved_note = self._viewmodel.notes.get(
            (student_id, criterion.id),
            "",
        )

        notes_input = self.rubric_correction_panel.notes_input

        notes_input.blockSignals(True)
        notes_input.setPlainText(saved_note)
        notes_input.blockSignals(False)

    def _on_student_selected(self) -> None:
        self._selected_criterion_index = None
        self.rubric_correction_panel.clear()

        selected_rows = self.student_grade_matrix.table.selectionModel().selectedRows()

        if not selected_rows:
            self.human_panel.clear()
            self.proxy_panel.clear()

            self.selected_student_label.setText(
                "Select a student from the matrix to view grading details."
            )
            return

        row = selected_rows[0].row()
        student_item = self.student_grade_matrix.table.item(row, 0)

        if student_item is None:
            return

        student_id = student_item.text()
        self.selected_student_label.setText(f"Selected student: {student_id}")

        rubric = self._viewmodel.rubric_definition
        assessment = next(
            (
                assessment
                for assessment in self._viewmodel.human_grades
                if str(assessment.student_id) == student_id
            ),
            None,
        )

        if rubric is None or assessment is None:
            self.human_panel.clear()
            self.proxy_panel.clear()

            self.human_details_label.setText(
                "Human grading details are unavailable for this student."
            )
        else:
            self._refresh_corrected_human_panel(int(student_id))

            self.proxy_panel.display_criteria(rubric, None)
            self.proxy_panel.total_label.setText("Total: — (proxy scores not yet calculated)")

    def _refresh_corrected_human_panel(self, student_id: int) -> None:
        rubric = self._viewmodel.rubric_definition

        if rubric is None:
            return

        assessment = next(
            (
                assessment
                for assessment in self._viewmodel.human_grades
                if assessment.student_id == student_id
            ),
            None,
        )

        if assessment is None:
            return

        scores = {score.criterion_id: score.points for score in assessment.criteria}

        has_corrections = False

        for criterion in rubric.criteria:
            correction = self._viewmodel.get_correction(
                student_id,
                criterion.id,
            )

            if correction is not None:
                scores[criterion.id] = correction
                has_corrections = True

        total = sum(score for score in scores.values() if score is not None)

        self.human_panel.display_criteria(rubric, scores)

        label = f"Total: {total:g} / {rubric.points_possible:g}"

        if has_corrections:
            label += " (corrected)"

        self.human_panel.total_label.setText(label)

        if self._selected_criterion_index is not None:
            self.human_panel.select_criterion(self._selected_criterion_index)

    def _on_notes_changed(self, notes: str) -> None:
        index = self._selected_criterion_index
        rubric = self._viewmodel.rubric_definition

        selected_rows = self.student_grade_matrix.table.selectionModel().selectedRows()

        if index is None or rubric is None or not selected_rows:
            return

        if not 0 <= index < len(rubric.criteria):
            return

        row = selected_rows[0].row()
        student_item = self.student_grade_matrix.table.item(row, 0)

        if student_item is None:
            return

        student_id = int(student_item.text())
        criterion_id = rubric.criteria[index].id
        key = (student_id, criterion_id)

        if notes.strip():
            self._viewmodel.notes[key] = notes
        else:
            self._viewmodel.notes.pop(key, None)

        self._viewmodel.save_current_corrections()

    def _on_correction_changed(self, corrected_score: float) -> None:
        index = self._selected_criterion_index
        rubric = self._viewmodel.rubric_definition

        selected_rows = self.student_grade_matrix.table.selectionModel().selectedRows()

        if index is None or rubric is None or not selected_rows:
            return

        if not 0 <= index < len(rubric.criteria):
            return

        row = selected_rows[0].row()
        student_item = self.student_grade_matrix.table.item(row, 0)

        if student_item is None:
            return

        student_id = int(student_item.text())
        criterion_id = rubric.criteria[index].id

        assessment = next(
            (
                assessment
                for assessment in self._viewmodel.human_grades
                if assessment.student_id == student_id
            ),
            None,
        )

        if assessment is None:
            return

        original_score = next(
            (score.points for score in assessment.criteria if score.criterion_id == criterion_id),
            None,
        )

        if original_score is not None and abs(corrected_score - original_score) < 0.0001:
            self._viewmodel.corrections.pop((student_id, criterion_id), None)
        else:
            self._viewmodel.set_correction(
                student_id=student_id,
                criterion_id=criterion_id,
                corrected_score=corrected_score,
            )

        self._refresh_corrected_human_panel(student_id)

        self.student_grade_matrix.update_corrected_row(
            assessment,
            rubric,
            self._viewmodel.corrections,
        )

        self._viewmodel.save_current_corrections()

    def _render_grading_status(self) -> None:
        if self._viewmodel.selected_assignment is None:
            self.status_label.setText("Select an assignment.")
            return

        messages = []

        if self._viewmodel.human_grades_error:
            messages.append(f"Human grades: {self._viewmodel.human_grades_error}")
        else:
            messages.append(f"Human grades: {len(self._viewmodel.human_grades)} assessments")

        if self._viewmodel.proxy_grades_error:
            messages.append(f"Proxy grades: {self._viewmodel.proxy_grades_error}")
        else:
            messages.append(f"Proxy grades: {len(self._viewmodel.proxy_grades)} submissions")

        if self._viewmodel.rubric_definition_error:
            messages.append(f"Student matrix: {self._viewmodel.rubric_definition_error}")

        self.status_label.setText("\n".join(messages))
