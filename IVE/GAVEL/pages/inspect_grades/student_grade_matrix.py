from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard


class StudentGradeMatrix(QWidget):
    """Displays student grades organized by rubric criterion."""

    def __init__(self, theme: ThemeContext) -> None:
        super().__init__()

        self._card = SectionCard(theme, "Student Grade Matrix")

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header.setHighlightSections(False)

        self.table.verticalHeader().setVisible(False)

        self._card.add_row(self.table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._card)

        self.clear()

    def clear(self) -> None:
        """Remove all displayed student and rubric data."""
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)

    def display(
        self,
        assessments: tuple[RubricAssessment, ...],
        rubric: RubricDefinition,
    ) -> None:
        """Populate the matrix with available human grading data."""
        self.clear()

        criteria = rubric.criteria
        headers = ["Student", "Human Total", "Proxy Total", "Difference"]

        headers.extend(f"C{index + 1}" for index in range(len(criteria)))

        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(assessments))
        for column in range(4):
            self.table.setColumnWidth(column, 130)

        for column in range(4, len(headers)):
            self.table.setColumnWidth(column, 75)

        for column, criterion in enumerate(criteria, start=4):
            header_item = self.table.horizontalHeaderItem(column)
            header_item.setToolTip(criterion.description)

        for row, assessment in enumerate(assessments):
            scores = {score.criterion_id: score.points for score in assessment.criteria}

            available_points = [points for points in scores.values() if points is not None]

            human_total = sum(available_points)

            self._set_item(row, 0, str(assessment.student_id))

            human_text = "—"

            if available_points:
                human_text = self._format_score(human_total)

                if any(scores.get(criterion.id) is None for criterion in criteria):
                    human_text += " (partial)"
            self._set_item(row, 1, human_text)
            self._set_item(row, 2, "—")
            self._set_item(row, 3, "—")

            for column, criterion in enumerate(criteria, start=4):
                points = scores.get(criterion.id)
                text = self._format_score(points) if points is not None else "—"
                self._set_item(row, column, text)

        self.table.clearSelection()

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, column, item)

    @staticmethod
    def _format_score(score: float) -> str:
        return f"{score:g}"
