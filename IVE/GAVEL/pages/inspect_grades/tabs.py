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
from GAVEL.pages.inspect_grades.student_grade_matrix import StudentGradeMatrix
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard
from GAVEL.pages.inspect_grades.grade_comparison_panel import GradeComparisonPanel


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
        self.status_label = QLabel()
        self.status_label.setProperty("role", "text_muted")
        self.status_label.setWordWrap(True)

        self.refresh_button = QPushButton("Refresh Assignments")
        self.refresh_button.clicked.connect(self.refresh)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.addRow("Assignment", self.assignment_combo)

        card.add_row(form_widget)
        card.add_row(self.refresh_button)
        card.add_row(self.status_label)

        self.add_section(card)

        self.student_grade_matrix = StudentGradeMatrix(theme)
        self.add_section(self.student_grade_matrix)

        self.comparison_card = SectionCard(theme, "Grade Comparison")

        self.selected_student_label = QLabel(
            "Select a student from the matrix to view grading details."
        )
        self.selected_student_label.setProperty("role", "text_muted")

        self.comparison_card.add_row(self.selected_student_label)

        panels_widget = QWidget()
        panels_layout = QHBoxLayout(panels_widget)
        panels_layout.setContentsMargins(0, 0, 0, 0)
        panels_layout.setSpacing(12)

        self.human_panel = GradeComparisonPanel(theme, "Human Grade")
        self.proxy_panel = GradeComparisonPanel(theme, "Proxy / Autograder Grade")

        self.human_panel.setMinimumWidth(350)
        self.proxy_panel.setMinimumWidth(350)

        self.human_details_label = self.human_panel.message_label
        self.proxy_details_label = self.proxy_panel.message_label

        panels_layout.addWidget(self.human_panel, 1)
        panels_layout.addWidget(self.proxy_panel, 1)

        human_scrollbar = self.human_panel.scroll_area.verticalScrollBar()
        proxy_scrollbar = self.proxy_panel.scroll_area.verticalScrollBar()

        human_scrollbar.valueChanged.connect(proxy_scrollbar.setValue)
        proxy_scrollbar.valueChanged.connect(human_scrollbar.setValue)

        self.human_panel.criterion_selected.connect(
            self._on_criterion_selected
        )
        self.proxy_panel.criterion_selected.connect(
            self._on_criterion_selected
        )

        self.comparison_card.add_row(panels_widget)
        self.add_section(self.comparison_card)

        self.student_grade_matrix.table.itemSelectionChanged.connect(
            self._on_student_selected
        )

        self.add_stretch()

        self.assignment_combo.currentIndexChanged.connect(self._on_assignment_changed)

        self._render_assignments()

    def set_course(self, course: CourseFolder | None) -> None:
        self._viewmodel.select_course(course)
        self.student_grade_matrix.clear()
        self._on_student_selected()
        self.selected_student_label.setText(
            "Select a student from the matrix to view grading details."
        )
        self._render_assignments()

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
        self._render_grading_status()

        self.student_grade_matrix.clear()
        self._on_student_selected()

        if self._viewmodel.rubric_definition is not None:
            self.student_grade_matrix.display(
                self._viewmodel.human_grades,
                self._viewmodel.rubric_definition,
            )

    def _on_criterion_selected(self, index: int) -> None:
        self.human_panel.select_criterion(index)
        self.proxy_panel.select_criterion(index)

    def _on_student_selected(self) -> None:
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
            scores = {
                score.criterion_id: score.points
                for score in assessment.criteria
            }

            total = sum(
                scores[criterion.id]
                for criterion in rubric.criteria
                if scores.get(criterion.id) is not None
            )

            self.human_panel.display_criteria(rubric, scores)
            self.proxy_panel.display_criteria(rubric, None)

            self.human_panel.total_label.setText(
                f"Total: {total:g} / {rubric.points_possible:g}"
            )
            self.proxy_panel.total_label.setText(
                "Total: — (proxy scores not yet calculated)"
            )


    def _render_grading_status(self) -> None:
        """Display the human and proxy grading data loading results."""
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
