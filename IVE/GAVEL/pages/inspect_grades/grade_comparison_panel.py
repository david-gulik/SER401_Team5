
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard
from GAVEL.app.dtos.rubric_definition import RubricDefinition



class CriterionCard(QFrame):

    clicked = pyqtSignal(int)

    def __init__(self, index: int) -> None:
        super().__init__()
        self.index = index
        self.setProperty("role", "grade_criterion")
        self.setProperty("selected", "false")
        self.setFixedHeight(64)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)

class GradeComparisonPanel(QWidget):
    criterion_selected = pyqtSignal(int)
    def __init__(self, theme: ThemeContext, title: str) -> None:
        super().__init__()

        self.card = SectionCard(theme, title)

        self.total_label = QLabel("Total: —")
        self.total_label.setProperty("role", "text_muted")
        self.card.add_row(self.total_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedHeight(300)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.content_layout.setSizeConstraint(
            QLayout.SizeConstraint.SetMinAndMaxSize
        )

        self.message_label = QLabel(
            "Select a student to view grading details."
        )
        self.message_label.setProperty("role", "text_muted")
        self.message_label.setWordWrap(True)

        self.content_layout.addWidget(self.message_label)

        self.criteria_widget = QWidget()
        self.criteria_layout = QVBoxLayout(self.criteria_widget)
        self.criteria_layout.setContentsMargins(0, 0, 0, 0)
        self.criteria_layout.setSpacing(8)
        self.criteria_layout.setSizeConstraint(
            QLayout.SizeConstraint.SetMinAndMaxSize
        )

        self.content_layout.addWidget(self.criteria_widget)
        self.content_layout.addStretch()

        self.scroll_area.setWidget(self.content_widget)
        self.card.add_row(self.scroll_area)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card)

    def display_criteria(
            self,
            rubric: RubricDefinition,
            scores: dict[str, float] | None,
    ) -> None:

        self.clear()
        self.message_label.setVisible(False)

        for index, criterion in enumerate(rubric.criteria, start=1):
            row_widget = CriterionCard(index - 1)
            row_widget.clicked.connect(self.criterion_selected.emit)

            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(8, 4, 8, 4)
            row_layout.setSpacing(8)

            description = QLabel(f"C{index}: {criterion.description}")
            description.setWordWrap(True)
            description.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            description.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            description.setToolTip(
                criterion.long_description or criterion.description
            )

            points = (
                scores.get(criterion.id)
                if scores is not None
                else None
            )

            if points is None:
                score_text = "—"
            else:
                score_text = f"{points:g} / {criterion.points:g}"

            score_label = QLabel(score_text)
            score_label.setMinimumWidth(65)
            score_label.setAlignment(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            )
            score_label.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )

            row_layout.addWidget(description, 1)
            row_layout.addWidget(score_label)

            self.criteria_layout.addWidget(row_widget)

    def clear(self) -> None:
        self.total_label.setText("Total: —")

        while self.criteria_layout.count():
            item = self.criteria_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.hide()
                widget.deleteLater()

        self.message_label.setText(
            "Select a student to view grading details."
        )
        self.message_label.setVisible(True)
        self.scroll_area.verticalScrollBar().setValue(0)

    def select_criterion(self, selected_index: int) -> None:
        for index in range(self.criteria_layout.count()):
            card = self.criteria_layout.itemAt(index).widget()

            if card is None:
                continue

            card.setProperty(
                "selected",
                "true" if index == selected_index else "false"
            )

            card.style().unpolish(card)
            card.style().polish(card)
            card.update()