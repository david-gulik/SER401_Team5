from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QFormLayout, QLabel, QPushButton, QWidget

from GAVEL.core.base_tab import ScrollableTab
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

        card = SectionCard(theme, "Course and Assignment Selection")

        self.course_combo = QComboBox()
        self.assignment_combo = QComboBox()
        self.status_label = QLabel()
        self.status_label.setProperty("role", "text_muted")
        self.status_label.setWordWrap(True)
        self.refresh_button = QPushButton("Refresh Courses")
        self.refresh_button.clicked.connect(self._load_courses)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.addRow("Course", self.course_combo)
        form.addRow("Assignment", self.assignment_combo)

        card.add_row(form_widget)
        card.add_row(self.refresh_button)
        card.add_row(self.status_label)

        self.add_section(card)
        self.add_stretch()

        self.course_combo.currentIndexChanged.connect(self._on_course_changed)
        self.assignment_combo.currentIndexChanged.connect(self._on_assignment_changed)

        self._load_courses()

    def _load_courses(self) -> None:
        previous_course = self._viewmodel.selected_course
        previous_assignment = self._viewmodel.selected_assignment

        self._viewmodel.load_courses()

        self.course_combo.blockSignals(True)
        self.course_combo.clear()
        self.course_combo.addItem("Select a course", None)

        for course in self._viewmodel.courses:
            self.course_combo.addItem(course.key.folder_name, course)

        selected_index = 0

        if previous_course is not None:
            for index, course in enumerate(self._viewmodel.courses, start=1):
                if course.key == previous_course.key:
                    selected_index = index
                    break

        self.course_combo.setCurrentIndex(selected_index)
        self.course_combo.blockSignals(False)

        self._on_course_changed(selected_index)

        if previous_assignment is not None and selected_index != 0:
            for index in range(1, self.assignment_combo.count()):
                assignment = self.assignment_combo.itemData(index)

                if assignment.canvas_id == previous_assignment.canvas_id:
                    self.assignment_combo.setCurrentIndex(index)
                    break

    def _on_course_changed(self, index: int) -> None:
        course = self.course_combo.itemData(index)
        self._viewmodel.select_course(course)

        self.assignment_combo.blockSignals(True)
        self.assignment_combo.clear()
        self.assignment_combo.addItem("Select an assignment", None)

        for assignment in self._viewmodel.assignments:
            self.assignment_combo.addItem(assignment.name, assignment)

        self.assignment_combo.blockSignals(False)
        self.assignment_combo.setEnabled(bool(self._viewmodel.assignments))

        if course is None:
            self.status_label.setText("Select a course to view assignments.")
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

        if assignment is None:
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

        self.status_label.setText("\n".join(messages))
