from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QFormLayout, QLabel, QPushButton, QWidget

from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard


class InspectGradesTab(ScrollableTab):
    """Picks an assignment of the active course; the page supplies the course."""

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
        self.refresh_button = QPushButton("Refresh Assignments")
        self.refresh_button.clicked.connect(self.refresh)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.addRow("Assignment", self.assignment_combo)

        card.add_row(form_widget)
        card.add_row(self.refresh_button)
        card.add_row(self.status_label)

        self.add_section(card)
        self.add_stretch()

        self.assignment_combo.currentIndexChanged.connect(self._on_assignment_changed)

        self._render_assignments()

    def set_course(self, course: CourseFolder | None) -> None:
        """The active course, from the page: when the tab is built and on every change."""
        self._viewmodel.select_course(course)
        self._render_assignments()

    def refresh(self) -> None:
        """Reread the course's assignments, keeping the selected one if it is still there."""
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
