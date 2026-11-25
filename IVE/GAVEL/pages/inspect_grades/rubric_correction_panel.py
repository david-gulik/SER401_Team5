from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QLabel,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.dtos.rubric_definition import RubricCriterionDefinition
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard


class RubricCorrectionPanel(QWidget):
    correction_changed = pyqtSignal(object)
    notes_changed = pyqtSignal(str)

    def __init__(self, theme: ThemeContext) -> None:
        super().__init__()

        self.card = SectionCard(theme, "Rubric Correction")

        self.student_label = QLabel("Student: —")
        self.criterion_label = QLabel("Criterion: —")
        self.original_grade_label = QLabel("Original Grade (Canvas): —")

        self.card.add_row(self.student_label)
        self.card.add_row(self.criterion_label)
        self.card.add_row(self.original_grade_label)

        self.grade_options_widget = QWidget()
        self.grade_options_layout = QVBoxLayout(self.grade_options_widget)
        self.grade_options_layout.setContentsMargins(0, 0, 0, 0)

        self.grade_options_label = QLabel("Set Corrected Grade")
        self.grade_options_layout.addWidget(self.grade_options_label)

        self.grade_buttons = QButtonGroup(self)
        self.grade_buttons.setExclusive(True)

        self.card.add_row(self.grade_options_widget)

        self.description_label = QLabel("Criterion Description")
        self.description_label.setWordWrap(True)

        self.description_text = QLabel("Select a criterion to view its description.")
        self.description_text.setWordWrap(True)

        self.card.add_row(self.description_label)
        self.card.add_row(self.description_text)

        self.notes_label = QLabel("Criteria Notes (optional)")
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Add a note about this correction...")
        self.notes_input.setFixedHeight(85)
        self.notes_input.textChanged.connect(self._on_notes_changed)

        self.card.add_row(self.notes_label)
        self.card.add_row(self.notes_input)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card)

        self.clear()

    def set_criterion(
        self,
        student_id: int,
        criterion: RubricCriterionDefinition,
        original_score: float | None,
    ) -> None:
        self.clear()

        self.student_label.setText(f"Student: {student_id}")
        self.criterion_label.setText(f"Criterion: {criterion.description}")

        maximum = f"{criterion.points:g}" if criterion.points is not None else "—"
        original = f"{original_score:g}" if original_score is not None else "—"

        self.original_grade_label.setText(f"Original Grade (Canvas): {original} / {maximum}")

        description = criterion.long_description or criterion.description
        self.description_text.setText(description)

        valid_ratings = [rating for rating in criterion.ratings if rating.points is not None]

        if not valid_ratings:
            message = QLabel("No predefined rubric ratings available.")
            self.grade_options_layout.addWidget(message)
        else:
            for rating in valid_ratings:
                button = QRadioButton(f"{rating.description}: {rating.points:g} / {maximum}")
                self.grade_buttons.addButton(button)
                self.grade_options_layout.addWidget(button)

                button.toggled.connect(
                    lambda checked, points=rating.points: (
                        self.correction_changed.emit(points) if checked else None
                    )
                )
                if original_score is not None and rating.points == original_score:
                    button.blockSignals(True)
                    button.setChecked(True)
                    button.blockSignals(False)

        self.notes_input.setEnabled(True)

    def _on_notes_changed(self) -> None:
        self.notes_changed.emit(self.notes_input.toPlainText())

    def clear(self) -> None:
        self.student_label.setText("Student: —")
        self.criterion_label.setText("Criterion: —")
        self.original_grade_label.setText("Original Grade (Canvas): —")
        self.description_text.setText("Select a criterion to view its description.")

        self.notes_input.blockSignals(True)
        self.notes_input.clear()
        self.notes_input.setEnabled(False)
        self.notes_input.blockSignals(False)

        for button in self.grade_buttons.buttons():
            self.grade_buttons.removeButton(button)

        while self.grade_options_layout.count() > 1:
            item = self.grade_options_layout.takeAt(1)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
