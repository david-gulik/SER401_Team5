from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import QLabel

from GAVEL.app.workspace.layout import CourseFolder, CourseKey
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.analytics.heat_map_card import HeatMapCard
from GAVEL.pages.analytics.score_distribution_card import ScoreDistributionCard
from GAVEL.pages.analytics.signed_error_histogram_card import SignedErrorHistogramCard
from GAVEL.pages.analytics.tabs import (
    _PLACEHOLDER_VISUALIZATIONS,
    GenerateReportCard,
    OverviewTab,
)
from GAVEL.ui_components.chart_canvas import ChartCanvas

_COURSE = CourseFolder(path=Path("unused"), key=CourseKey.parse("ser222_25sc_12345"))


def _tab(theme) -> OverviewTab:
    return OverviewTab(theme, build_dataset_readers())


def test_overview_tab_starts_with_empty_placeholder_charts(qapp, theme):
    tab = _tab(theme)

    canvases = tab.findChildren(ChartCanvas)

    assert len(canvases) == 3
    assert not any(canvas.is_showing_chart() for canvas in canvases)


def test_overview_tab_includes_the_signed_error_histogram_card(qapp, theme):
    tab = _tab(theme)

    assert len(tab.findChildren(SignedErrorHistogramCard)) == 1


def test_overview_tab_includes_the_generate_report_card(qapp, theme):
    tab = _tab(theme)

    assert len(tab.findChildren(GenerateReportCard)) == 1


def test_overview_tab_hands_the_active_course_to_the_generate_report_card(qapp, theme):
    tab = _tab(theme)

    tab.set_course(_COURSE)

    [card] = tab.findChildren(GenerateReportCard)
    assert card._selected_course() == _COURSE


def test_changing_the_course_empties_every_report_card(qapp, theme, tmp_path: Path):
    tab = _tab(theme)
    report = tmp_path / "ser334_m2.json"
    row = {"student_identifier": "s0", "human_score": 1.0, "proxy_score": 0.5, "signed_error": 0.5}
    report.write_text(
        json.dumps({"rows": [row], "unmatched_submissions": [], "failed_submissions": []}),
        encoding="utf-8",
    )
    [histogram] = tab.findChildren(SignedErrorHistogramCard)
    histogram.load_report(report)
    assert histogram.findChild(ChartCanvas).is_showing_chart()

    tab.set_course(_COURSE)

    assert not any(canvas.is_showing_chart() for canvas in tab.findChildren(ChartCanvas))
    assert histogram._status.text() == "No report chosen yet."


def test_overview_tab_includes_the_heat_map_card(qapp, theme):
    tab = _tab(theme)

    assert len(tab.findChildren(HeatMapCard)) == 1


def test_overview_tab_includes_the_score_distribution_card(qapp, theme):
    tab = _tab(theme)

    assert len(tab.findChildren(ScoreDistributionCard)) == 1


def test_overview_tab_includes_a_placeholder_for_every_other_visualization(qapp, theme):
    tab = _tab(theme)

    placeholder_labels = [w for w in tab.findChildren(QLabel) if w.text() == "Not yet implemented."]

    assert len(placeholder_labels) == len(_PLACEHOLDER_VISUALIZATIONS)
