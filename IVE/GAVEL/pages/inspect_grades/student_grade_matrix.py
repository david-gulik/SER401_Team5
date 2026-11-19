from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard


class ComparisonCellDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        brush = index.data(Qt.ItemDataRole.BackgroundRole)

        if not isinstance(brush, QBrush):
            return

        if brush.style() == Qt.BrushStyle.NoBrush:
            return

        painter.save()

        painter.fillRect(
            option.rect.adjusted(0, 0, 0, -1),
            brush,
        )

        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(
            option.rect.adjusted(8, 0, -4, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            str(index.data(Qt.ItemDataRole.DisplayRole) or ""),
        )

        painter.restore()


class StudentGradeMatrix(QWidget):
    def __init__(self, theme: ThemeContext) -> None:
        super().__init__()

        self._card = SectionCard(theme, "Grade Matrix")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by student ID...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_rows)

        self.mismatch_checkbox = QCheckBox("Show only mismatches")
        self.mismatch_checkbox.toggled.connect(self._filter_rows)

        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(12)

        filter_layout.addWidget(self.search_input, 1)
        filter_layout.addWidget(self.mismatch_checkbox)

        self._card.add_row(filter_widget)

        self.table = QTableWidget()
        self.table.setItemDelegate(ComparisonCellDelegate(self.table))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header.setHighlightSections(False)

        self.table.verticalHeader().setVisible(False)

        self._card.add_row(self.table)

        self.empty_label = QLabel("No students match the current filters.")
        self.empty_label.setProperty("role", "text_muted")
        self.empty_label.setVisible(False)

        self._card.add_row(self.empty_label)

        self.legend_label = QLabel()
        self.legend_label.setProperty("role", "text_muted")
        self.legend_label.setWordWrap(True)

        self._card.add_row(self.legend_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._card)

        self._proxy_scores_by_student: dict[int, dict[str, float]] = {}
        self._proxy_scores_supplied = False

        self.clear()

    def clear(self) -> None:
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.legend_label.setText("Comparisons will appear when proxy rubric scores are available.")
        self.search_input.clear()
        self.mismatch_checkbox.setChecked(False)
        self.empty_label.setVisible(False)
        self._proxy_scores_by_student = {}
        self._proxy_scores_supplied = False

    def display(
        self,
        assessments: tuple[RubricAssessment, ...],
        rubric: RubricDefinition,
        proxy_scores_by_student: dict[int, dict[str, float]] | None = None,
    ) -> None:
        self.clear()
        self._proxy_scores_supplied = proxy_scores_by_student is not None

        self._proxy_scores_by_student = (
            {student_id: dict(scores) for student_id, scores in proxy_scores_by_student.items()}
            if proxy_scores_by_student is not None
            else {}
        )

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

        matches = 0
        mismatches = 0

        for row, assessment in enumerate(assessments):
            scores = {score.criterion_id: score.points for score in assessment.criteria}

            proxy_scores = (
                proxy_scores_by_student.get(assessment.student_id, {})
                if proxy_scores_by_student is not None
                else {}
            )

            available_points = [
                scores.get(criterion.id)
                for criterion in criteria
                if scores.get(criterion.id) is not None
            ]

            human_total = sum(available_points)
            human_complete = bool(criteria) and all(
                scores.get(criterion.id) is not None for criterion in criteria
            )

            self._set_item(row, 0, str(assessment.student_id))

            has_mismatch = any(
                scores.get(criterion.id) is not None
                and proxy_scores.get(criterion.id) is not None
                and abs(scores[criterion.id] - proxy_scores[criterion.id]) > 0.0001
                for criterion in criteria
            )

            self.table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                has_mismatch,
            )

            human_text = "—"

            if available_points:
                human_text = self._format_score(human_total)

                if not human_complete:
                    human_text += " (partial)"

            self._set_item(row, 1, human_text)

            proxy_complete = bool(criteria) and all(
                proxy_scores.get(criterion.id) is not None for criterion in criteria
            )

            proxy_text = "—"
            difference_text = "—"

            if proxy_complete:
                proxy_total = sum(proxy_scores[criterion.id] for criterion in criteria)
                proxy_text = self._format_score(proxy_total)

                if human_complete:
                    difference = human_total - proxy_total
                    difference_text = self._format_score(difference)

            self._set_item(row, 2, proxy_text)
            self._set_item(row, 3, difference_text)

            for column, criterion in enumerate(criteria, start=4):
                human_points = scores.get(criterion.id)
                proxy_points = proxy_scores.get(criterion.id)

                if proxy_points is None:
                    text = self._format_score(human_points) if human_points is not None else "—"
                else:
                    human_score_text = (
                        self._format_score(human_points) if human_points is not None else "—"
                    )
                    text = f"{human_score_text}/{self._format_score(proxy_points)}"

                self._set_item(row, column, text)

                if human_points is not None and proxy_points is not None:
                    item = self.table.item(row, column)

                    if abs(human_points - proxy_points) <= 0.0001:
                        item.setBackground(QColor("#246B48"))
                        matches += 1
                    else:
                        item.setBackground(QColor("#913D45"))
                        mismatches += 1

        if proxy_scores_by_student is not None:
            self.legend_label.setText(
                f'<span style="color:#55C98A;">■</span> Match: {matches}'
                f'    <span style="color:#F07880;">■</span> Mismatch: {mismatches}'
                "    <span>—</span> Unavailable comparisons are not counted"
            )
            self.legend_label.setTextFormat(Qt.TextFormat.RichText)

        self._filter_rows()

        self.table.clearSelection()

    def update_corrected_row(
        self,
        assessment: RubricAssessment,
        rubric: RubricDefinition,
        corrections: dict[tuple[int, str], float],
    ) -> None:
        student_id = assessment.student_id

        row = next(
            (
                index
                for index in range(self.table.rowCount())
                if self.table.item(index, 0) is not None
                and self.table.item(index, 0).text() == str(student_id)
            ),
            None,
        )

        if row is None:
            return

        original_scores = {score.criterion_id: score.points for score in assessment.criteria}

        total = 0.0
        has_scores = False
        has_corrections = False
        complete = bool(rubric.criteria)

        for column, criterion in enumerate(rubric.criteria, start=4):
            original = original_scores.get(criterion.id)
            correction = corrections.get((student_id, criterion.id))

            corrected = correction if correction is not None else original

            if corrected is None:
                complete = False
            else:
                total += corrected
                has_scores = True

            is_corrected = correction is not None and correction != original

            if is_corrected:
                has_corrections = True

            item = self.table.item(row, column)

            if item is None:
                continue

            text = self._format_score(corrected) if corrected is not None else "—"

            if is_corrected:
                text += "*"
                original_text = self._format_score(original) if original is not None else "—"
                item.setToolTip(
                    f"Original Canvas grade: {original_text}\n"
                    f"Corrected grade: {self._format_score(corrected)}"
                )
            else:
                item.setToolTip("")

            item.setText(text)

        proxy_scores = self._proxy_scores_by_student.get(student_id, {})

        proxy_complete = bool(rubric.criteria) and all(
            proxy_scores.get(criterion.id) is not None for criterion in rubric.criteria
        )

        difference_item = self.table.item(row, 3)

        if difference_item is not None:
            difference_text = "—"

            if proxy_complete and complete:
                proxy_total = sum(proxy_scores[criterion.id] for criterion in rubric.criteria)
                difference_text = self._format_score(total - proxy_total)

            difference_item.setText(difference_text)

        has_mismatch = False

        for column, criterion in enumerate(rubric.criteria, start=4):
            item = self.table.item(row, column)

            if item is None:
                continue

            original = original_scores.get(criterion.id)
            correction = corrections.get((student_id, criterion.id))
            human_points = correction if correction is not None else original
            proxy_points = proxy_scores.get(criterion.id)

            human_text = self._format_score(human_points) if human_points is not None else "—"

            is_corrected = correction is not None and correction != original

            if is_corrected:
                human_text += "*"

            if proxy_points is not None:
                item.setText(f"{human_text}/{self._format_score(proxy_points)}")
            else:
                item.setText(human_text)

            if human_points is not None and proxy_points is not None:
                if abs(human_points - proxy_points) <= 0.0001:
                    item.setBackground(QColor("#246B48"))
                else:
                    item.setBackground(QColor("#913D45"))
                    has_mismatch = True
            else:
                item.setBackground(QBrush())

        student_item = self.table.item(row, 0)

        if student_item is not None:
            student_item.setData(
                Qt.ItemDataRole.UserRole,
                has_mismatch,
            )

        total_item = self.table.item(row, 1)

        if total_item is not None:
            total_text = self._format_score(total) if has_scores else "—"

            if has_scores and not complete:
                total_text += " (partial)"

            if has_corrections:
                total_text += "*"
                total_item.setToolTip("Includes temporary rubric corrections.")
            else:
                total_item.setToolTip("")

            total_item.setText(total_text)

        if self._proxy_scores_supplied:
            matches = 0
            mismatches = 0

            for table_row in range(self.table.rowCount()):
                for column in range(4, self.table.columnCount()):
                    item = self.table.item(table_row, column)

                    if item is None:
                        continue

                    color = item.background().color()

                    if color == QColor("#246B48"):
                        matches += 1
                    elif color == QColor("#913D45"):
                        mismatches += 1

            self.legend_label.setText(
                f'<span style="color:#55C98A;">■</span> Match: {matches}'
                f'    <span style="color:#F07880;">■</span> Mismatch: {mismatches}'
                "    <span>—</span> Unavailable comparisons are not counted"
            )

        self._filter_rows()

    def _filter_rows(self) -> None:
        search_text = self.search_input.text().strip().casefold()
        only_mismatches = self.mismatch_checkbox.isChecked()
        visible_count = 0

        for row in range(self.table.rowCount()):
            student_item = self.table.item(row, 0)

            if student_item is None:
                self.table.setRowHidden(row, True)
                continue

            matches_search = search_text in student_item.text().casefold()
            has_mismatch = bool(student_item.data(Qt.ItemDataRole.UserRole))

            show_row = matches_search and (not only_mismatches or has_mismatch)

            self.table.setRowHidden(row, not show_row)
            if show_row:
                visible_count += 1

            if not show_row and self.table.currentRow() == row:
                self.table.clearSelection()
                self.table.setCurrentCell(-1, -1)

        self.empty_label.setVisible(self.table.rowCount() > 0 and visible_count == 0)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, column, item)

    @staticmethod
    def _format_score(score: float) -> str:
        return f"{score:g}"
