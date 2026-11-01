from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from GAVEL.pages.analytics.signed_error_histogram_viewmodel import (
    SignedErrorHistogramData,
    SignedErrorHistogramViewModel,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.chart_canvas import ChartCanvas
from GAVEL.ui_components.hint_icon import hint_icon
from GAVEL.ui_components.section_card import SectionCard

_NO_REPORT = "No report chosen yet."


class SignedErrorHistogramCard(QWidget):
    """Loads a signed-error report, chosen by the user, and charts its distribution."""

    def __init__(
        self,
        theme: ThemeContext,
        view_model: SignedErrorHistogramViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._view_model = view_model or SignedErrorHistogramViewModel()

        self._card = SectionCard(self._theme, "Signed Error Histogram")
        self._card.add_title_suffix(hint_icon("Requires a signed-error report file."))

        choose_button = QPushButton("Choose report…")
        choose_button.clicked.connect(self._choose_report)
        self._card.add_action(choose_button)

        self._status = QLabel(_NO_REPORT)
        self._status.setProperty("role", "text_muted")
        self._card.add_row(self._status)

        self._canvas = ChartCanvas(
            self._theme, placeholder_text="Choose a signed-error report to see its histogram."
        )
        self._card.add_row(self._canvas)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._card)

    def _choose_report(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a signed-error report", "", "JSON files (*.json)"
        )
        if not path:
            return
        self.load_report(Path(path))

    def load_report(self, report_path: Path) -> None:
        """Loads a report and displays its histogram, or reports why it could not."""
        try:
            data = self._view_model.load(report_path)
        except Exception as exc:
            self._status.setText(f"Could not read {report_path.name}: {exc}")
            self._canvas.clear()
            return

        if data.bins:
            self._status.setText(f"Showing {report_path.name}")
        else:
            self._status.setText(f"{report_path.name} has no scored submissions to chart.")
        self.display(data)

    def clear(self) -> None:
        """Back to the empty state, as before any report was chosen."""
        self._status.setText(_NO_REPORT)
        self._canvas.clear()

    def display(self, data: SignedErrorHistogramData) -> None:
        self._canvas.clear()
        if not data.bins:
            return

        axes = self._canvas.figure.add_subplot()
        axes.bar(
            [b.lower for b in data.bins],
            [b.count for b in data.bins],
            width=[b.upper - b.lower for b in data.bins],
            align="edge",
        )
        axes.set_xlabel("Signed error (human minus proxy)")
        axes.set_ylabel("Submissions")
        axes.set_title(data.module_label)
        self._canvas.draw()
