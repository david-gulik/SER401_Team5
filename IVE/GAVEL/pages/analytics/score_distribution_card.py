from __future__ import annotations

from pathlib import Path

from matplotlib.patches import Patch
from PyQt6.QtWidgets import QFileDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from GAVEL.pages.analytics.score_distribution_viewmodel import (
    ScoreDistributionData,
    ScoreDistributionViewModel,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.chart_canvas import ChartCanvas
from GAVEL.ui_components.hint_icon import hint_icon
from GAVEL.ui_components.section_card import SectionCard

_HUMAN_COLOR = "C0"
_PROXY_COLOR = "C1"
_GROUP_WIDTH = 3  # positions per group: human, proxy, one gap


class ScoreDistributionCard(QWidget):
    """Loads a heat map report, chosen by the user, and charts human vs proxy
    score distributions side by side, pooled by requirement group."""

    def __init__(
        self,
        theme: ThemeContext,
        view_model: ScoreDistributionViewModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._view_model = view_model or ScoreDistributionViewModel()

        self._card = SectionCard(self._theme, "Score Distribution Boxplot")
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
        """Loads a report and displays its score distributions, or reports why it could not."""
        try:
            data = self._view_model.load(report_path)
        except Exception as exc:
            self._status.setText(f"Could not read {report_path.name}: {exc}")
            self._canvas.clear()
            return

        self._status.setText(f"Showing {report_path.name}")
        self.display(data)

    def display(self, data: ScoreDistributionData) -> None:
        self._canvas.clear()
        if not data.groups:
            return

        positions: list[int] = []
        box_data: list[tuple[float, ...]] = []
        for i, group in enumerate(data.groups):
            base = i * _GROUP_WIDTH
            positions.extend((base + 1, base + 2))
            box_data.extend((group.human_points, group.proxy_points))

        axes = self._canvas.figure.add_subplot()
        boxes = axes.boxplot(box_data, positions=positions, patch_artist=True, widths=0.6)
        for i, box in enumerate(boxes["boxes"]):
            box.set_facecolor(_HUMAN_COLOR if i % 2 == 0 else _PROXY_COLOR)

        for i, (group, result) in enumerate(zip(data.groups, data.significance, strict=True)):
            group_max = max(*group.human_points, *group.proxy_points)
            axes.text(
                i * _GROUP_WIDTH + 1.5,
                group_max,
                f"U={result.u_statistic:g}\np={result.p_value:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

        axes.margins(y=0.15)  # headroom so the significance text isn't clipped

        group_centers = [i * _GROUP_WIDTH + 1.5 for i in range(len(data.groups))]
        axes.set_xticks(group_centers)
        axes.set_xticklabels([group.group for group in data.groups], rotation=30, ha="right")
        axes.set_ylabel("Points")
        axes.set_title(data.report_label)
        axes.legend(
            handles=[
                Patch(facecolor=_HUMAN_COLOR, label="Human"),
                Patch(facecolor=_PROXY_COLOR, label="Proxy"),
            ]
        )
        self._canvas.draw()
