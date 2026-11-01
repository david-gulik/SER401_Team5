from __future__ import annotations

import json
from pathlib import Path

from GAVEL.pages.analytics.score_distribution_card import ScoreDistributionCard
from GAVEL.ui_components.chart_canvas import ChartCanvas


def _write_report(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")


def test_starts_with_no_chart_shown(qapp, theme):
    card = ScoreDistributionCard(theme)

    canvas = card.findChild(ChartCanvas)

    assert not canvas.is_showing_chart()


def test_clear_returns_to_the_empty_state(qapp, theme, tmp_path: Path):
    path = tmp_path / "report.json"
    _write_report(path, [{"criterion": "main menu", "human_points": 1.0, "proxy_points": 2.0}])
    card = ScoreDistributionCard(theme)
    card.load_report(path)

    card.clear()

    assert not card.findChild(ChartCanvas).is_showing_chart()
    assert card._status.text() == "No report chosen yet."


def test_loading_a_report_draws_a_chart(qapp, theme, tmp_path: Path):
    path = tmp_path / "report.json"
    _write_report(
        path,
        [{"criterion": "main menu", "human_points": 1.0, "proxy_points": 2.0}],
    )
    card = ScoreDistributionCard(theme)

    card.load_report(path)

    canvas = card.findChild(ChartCanvas)
    assert canvas.is_showing_chart()


def test_loading_a_report_annotates_each_group_with_its_significance(qapp, theme, tmp_path: Path):
    path = tmp_path / "report.json"
    _write_report(
        path,
        [
            {"criterion": "main menu", "human_points": 1.0, "proxy_points": 2.0},
            {"criterion": "main menu", "human_points": 2.0, "proxy_points": 1.0},
        ],
    )
    card = ScoreDistributionCard(theme)

    card.load_report(path)

    axes = card._canvas.figure.axes[0]
    annotations = [t.get_text() for t in axes.texts]
    assert len(annotations) == 1
    assert "U=" in annotations[0]
    assert "p=" in annotations[0]


def test_unreadable_report_is_handled_without_crashing(qapp, theme, tmp_path: Path):
    path = tmp_path / "missing.json"
    card = ScoreDistributionCard(theme)

    card.load_report(path)

    canvas = card.findChild(ChartCanvas)
    assert not canvas.is_showing_chart()


def test_empty_report_shows_no_chart(qapp, theme, tmp_path: Path):
    path = tmp_path / "report.json"
    _write_report(path, [])
    card = ScoreDistributionCard(theme)

    card.load_report(path)

    canvas = card.findChild(ChartCanvas)
    assert not canvas.is_showing_chart()
    assert "no scored submissions" in card._status.text()


class _RaisingViewModel:
    def load(self, report_path: Path):
        raise RuntimeError("boom")


def test_an_unexpected_exception_is_reported_without_crashing(qapp, theme, tmp_path: Path):
    card = ScoreDistributionCard(theme, _RaisingViewModel())

    card.load_report(tmp_path / "whatever.json")

    canvas = card.findChild(ChartCanvas)
    assert not canvas.is_showing_chart()
    assert "boom" in card._status.text()
