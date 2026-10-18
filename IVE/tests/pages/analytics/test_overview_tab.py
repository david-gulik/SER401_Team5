from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QLabel

from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.analytics.tabs import (
    _PLACEHOLDER_VISUALIZATIONS,
    GenerateReportCard,
    OverviewTab,
    SignedErrorHistogramCard,
)
from GAVEL.ui_components.chart_canvas import ChartCanvas


def _tab(theme, tmp_path: Path) -> OverviewTab:
    return OverviewTab(theme, build_dataset_readers(), tmp_path / "workspace")


def test_overview_tab_starts_with_an_empty_placeholder_chart(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)

    canvases = tab.findChildren(ChartCanvas)

    assert len(canvases) == 1
    assert not canvases[0].is_showing_chart()


def test_overview_tab_includes_the_signed_error_histogram_card(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)

    assert len(tab.findChildren(SignedErrorHistogramCard)) == 1


def test_overview_tab_includes_the_generate_report_card(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)

    assert len(tab.findChildren(GenerateReportCard)) == 1


def test_overview_tab_includes_a_placeholder_for_every_other_visualization(
    qapp, theme, tmp_path: Path
):
    tab = _tab(theme, tmp_path)

    placeholder_labels = [w for w in tab.findChildren(QLabel) if w.text() == "Not yet implemented."]

    assert len(placeholder_labels) == len(_PLACEHOLDER_VISUALIZATIONS)
