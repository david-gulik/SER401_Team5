from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from GAVEL.pages.analytics.r_squared_viewmodel import RSquaredData, RSquaredViewModel
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.chart_canvas import ChartCanvas
from GAVEL.ui_components.hint_icon import hint_icon
from GAVEL.ui_components.section_card import SectionCard

_NO_REPORT = "No report chosen yet."


class RSquaredCard(QWidget):
    """Loads an r-squared report and charts both checks that it carries.
    Autograder test redundancy is drawn as a horizontal bar per test pair.
    The cross-assessment comparison is a single value and is described in the chart's
    title.
    """

    def __init__(
        self,
        theme: ThemeContext,
        view_model: RSquaredViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._view_model = view_model or RSquaredViewModel()

        self._card = SectionCard(self._theme, "R² (Test Redundancy and Cross-Assessment)")
        self._card.add_title_suffix(
            hint_icon(
                "Requires an r-squared report file with autograder test-pair redundancy and one cross-assessment comparison."
            )
        )

        choose_button = QPushButton("Choose report…")
        choose_button.clicked.connect(self._choose_report)
        self._card.add_action(choose_button)

        self._status = QLabel(_NO_REPORT)
        self._status.setProperty("role", "text_muted")
        self._card.add_row(self._status)

        self._canvas = ChartCanvas(
            self._theme, placeholder_text="Choose an r-squared report to see it."
        )
        self._card.add_row(self._canvas)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._card)

    def clear_title(self) -> None:
        """Empties this card's own title text, for a caller that already shows it."""
        self._card.clear_title()

    def _choose_report(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose an r-squared report", "", "JSON files (*.json)"
        )
        if not path:
            return
        self.load_report(Path(path))

    def load_report(self, report_path: Path) -> None:
        """Loads a report and displays its charts, or reports why it could not."""
        try:
            data = self._view_model.load(report_path)
        except Exception as exc:
            self._status.setText(f"Could not read {report_path.name}: {exc}")
            self._canvas.clear()
            return

        if data.test_pairs:
            self._status.setText(f"Showing {report_path.name}")
        else:
            self._status.setText(f"{report_path.name} has no test pairs to chart.")
        self.display(data)

    def clear(self) -> None:
        """Back to the empty state, as before any report was chosen."""
        self._status.setText(_NO_REPORT)
        self._canvas.clear()

    def display(self, data: RSquaredData) -> None:
        self._canvas.clear()
        if not data.test_pairs:
            return

        sorted_pairs = sorted(data.test_pairs, key=lambda pair: pair.r_squared, reverse=True)
        labels = [f"{pair.test_a} vs {pair.test_b}" for pair in sorted_pairs]
        values = [pair.r_squared for pair in sorted_pairs]

        axes = self._canvas.figure.add_subplot()
        axes.barh(labels, values, color="C0")
        axes.invert_yaxis()
        axes.set_xlim(0, 1)
        axes.set_xlabel("r²")
        axes.set_ylabel("Test pair")
        cross = data.cross_assessment
        axes.set_title(
            f"Cross-assessment: {cross.column_a} vs {cross.column_b} (r² = {cross.r_squared:.2f})"
        )
        self._canvas.draw()
