from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel, QPushButton

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


def _tab(theme, tmp_path: Path) -> OverviewTab:
    settings = QSettings(str(tmp_path / "gavel.ini"), QSettings.Format.IniFormat)
    return OverviewTab(theme, build_dataset_readers(), settings)


def test_overview_tab_starts_with_empty_placeholder_charts(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)

    canvases = tab.findChildren(ChartCanvas)

    assert len(canvases) == 3
    assert not any(canvas.is_showing_chart() for canvas in canvases)


def test_overview_tab_includes_the_signed_error_histogram_card(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)

    assert len(tab.findChildren(SignedErrorHistogramCard)) == 1


def test_overview_tab_includes_the_generate_report_card(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)

    assert len(tab.findChildren(GenerateReportCard)) == 1


def test_overview_tab_hands_the_active_course_to_the_generate_report_card(
    qapp, theme, tmp_path: Path
):
    tab = _tab(theme, tmp_path)

    tab.set_course(_COURSE)

    [card] = tab.findChildren(GenerateReportCard)
    assert card._selected_course() == _COURSE


def test_changing_the_course_empties_every_report_card(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)
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


def test_overview_tab_includes_the_heat_map_card(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)

    assert len(tab.findChildren(HeatMapCard)) == 1


def test_overview_tab_includes_the_score_distribution_card(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)

    assert len(tab.findChildren(ScoreDistributionCard)) == 1


def test_overview_tab_includes_a_placeholder_for_every_other_visualization(
    qapp, theme, tmp_path: Path
):
    tab = _tab(theme, tmp_path)

    placeholder_labels = [w for w in tab.findChildren(QLabel) if w.text() == "Not yet implemented."]

    assert len(placeholder_labels) == len(_PLACEHOLDER_VISUALIZATIONS)


def test_the_dock_layout_is_remembered_for_the_next_launch(qapp, theme, tmp_path: Path):
    settings_path = str(tmp_path / "gavel.ini")
    tab = OverviewTab(
        theme,
        build_dataset_readers(),
        QSettings(settings_path, QSettings.Format.IniFormat),
    )
    tab._save_dock_layout()
    saved_layout = tab._dock_host.saveState()

    relaunched = OverviewTab(
        theme,
        build_dataset_readers(),
        QSettings(settings_path, QSettings.Format.IniFormat),
    )

    assert relaunched._dock_host.saveState() == saved_layout


def test_a_fresh_launch_with_no_saved_layout_still_builds_the_default_grid(
    qapp, theme, tmp_path: Path
):
    tab = _tab(theme, tmp_path)

    assert len(tab.findChildren(HeatMapCard)) == 1


def _manage_analytics_menu(tab: OverviewTab):
    [button] = [b for b in tab.findChildren(QPushButton) if b.text() == "Manage Analytics"]
    return button.menu()


def test_manage_analytics_lists_every_card_checked_by_default(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)
    # A dock's toggle action reflects real visibility, which Qt only
    # resolves once the widget is actually shown.
    tab.show()

    actions = _manage_analytics_menu(tab).actions()

    assert len(actions) == 4 + len(_PLACEHOLDER_VISUALIZATIONS)
    assert all(action.isCheckable() and action.isChecked() for action in actions)


def test_unchecking_a_card_in_manage_analytics_hides_it(qapp, theme, tmp_path: Path):
    tab = _tab(theme, tmp_path)
    [heat_map_action] = [a for a in _manage_analytics_menu(tab).actions() if a.text() == "Heat Map"]

    heat_map_action.setChecked(False)

    [heat_map_card] = tab.findChildren(HeatMapCard)
    assert not heat_map_card.isVisible()
