from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QFormLayout, QLabel, QPushButton, QWidget

from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.core.base_tab import ScrollableTab
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

        self.add_stretch()

        self.assignment_combo.currentIndexChanged.connect(self._on_assignment_changed)
        self.autograder_zip_combo.currentIndexChanged.connect(self._on_autograder_zip_changed)

        self._render_assignments()
        self._render_autograder_zips()

    def set_course(self, course: CourseFolder | None) -> None:
        self._viewmodel.select_course(course)
        self.student_grade_matrix.clear()
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

        if self._viewmodel.rubric_definition is not None:
            self.student_grade_matrix.display(
                self._viewmodel.human_grades,
                self._viewmodel.rubric_definition,
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
