from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from GAVEL.app.dtos.disagreement_category import DisagreementCategory
from GAVEL.pages.analytics.heat_map_viewmodel import HeatMapData, HeatMapViewModel
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.chart_canvas import ChartCanvas
from GAVEL.ui_components.hint_icon import hint_icon
from GAVEL.ui_components.section_card import SectionCard

_CATEGORIES = tuple(DisagreementCategory)


class HeatMapCard(QWidget):
    """Loads a heat map report, chosen by the user, and charts per-criterion disagreement."""

    def __init__(
        self,
        theme: ThemeContext,
        view_model: HeatMapViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._view_model = view_model or HeatMapViewModel()

        self._card = SectionCard(self._theme, "Human vs Autograder Heat Map")
        self._card.add_title_suffix(
            hint_icon(
                "Requires a heat map report file with per-student, per-criterion human and "
                "proxy scores."
            )
        )

        choose_button = QPushButton("Choose report…")
        choose_button.clicked.connect(self._choose_report)
        self._card.add_action(choose_button)

        self._status = QLabel("No report chosen yet.")
        self._status.setProperty("role", "text_muted")
        self._card.add_row(self._status)

        self._canvas = ChartCanvas(
            self._theme, placeholder_text="Choose a heat map report to see it."
        )
        self._card.add_row(self._canvas)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._card)

    def _choose_report(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a heat map report", "", "JSON files (*.json)"
        )
        if not path:
            return
        self.load_report(Path(path))

    def load_report(self, report_path: Path) -> None:
        """Loads a report and displays its heat map, or reports why it could not."""
        try:
            data = self._view_model.load(report_path)
        except Exception as exc:
            self._status.setText(f"Could not read {report_path.name}: {exc}")
            self._canvas.clear()
            return

        self._status.setText(f"Showing {report_path.name}")
        self.display(data)

    def display(self, data: HeatMapData) -> None:
        self._canvas.clear()
        if not data.cells:
            return

        criteria: list[str] = []
        for cell in data.cells:
            if cell.criterion not in criteria:
                criteria.append(cell.criterion)

        grid = [[0 for _ in _CATEGORIES] for _ in criteria]
        for cell in data.cells:
            row = criteria.index(cell.criterion)
            col = _CATEGORIES.index(cell.category)
            grid[row][col] = cell.count

        axes = self._canvas.figure.add_subplot()
        image = axes.imshow(grid, aspect="auto", cmap="Blues")
        axes.set_xticks(range(len(_CATEGORIES)))
        axes.set_xticklabels([category.value for category in _CATEGORIES])
        axes.set_yticks(range(len(criteria)))
        axes.set_yticklabels(criteria)
        axes.set_xlabel("Disagreement category")
        axes.set_ylabel("Rubric criterion")
        axes.set_title(data.report_label)
        for row_index, row in enumerate(grid):
            for col_index, count in enumerate(row):
                axes.text(col_index, row_index, str(count), ha="center", va="center")
        self._canvas.figure.colorbar(image, ax=axes, label="Students")
        self._canvas.draw()
