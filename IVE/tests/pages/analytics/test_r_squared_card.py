from __future__ import annotations

import json
from pathlib import Path

from GAVEL.pages.analytics.r_squared_card import RSquaredCard
from GAVEL.ui_components.chart_canvas import ChartCanvas


def _write_report(path: Path, test_pairs: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "test_pairs": test_pairs,
                "cross_assessment": {
                    "column_a": "Programming",
                    "column_b": "Quiz",
                    "r_squared": 0.5,
                },
            }
        ),
        encoding="utf-8",
    )


def test_starts_with_no_chart_shown(qapp, theme):
    card = RSquaredCard(theme)

    canvas = card.findChild(ChartCanvas)

    assert not canvas.is_showing_chart()


def test_loading_a_report_draws_a_chart(qapp, theme, tmp_path: Path):
    path = tmp_path / "report.json"
    _write_report(path, [{"test_a": "A", "test_b": "B", "r_squared": 0.9}])
    card = RSquaredCard(theme)

    card.load_report(path)

    canvas = card.findChild(ChartCanvas)
    assert canvas.is_showing_chart()


def test_clear_returns_to_the_empty_state(qapp, theme, tmp_path: Path):
    path = tmp_path / "report.json"
    _write_report(path, [{"test_a": "A", "test_b": "B", "r_squared": 0.9}])
    card = RSquaredCard(theme)
    card.load_report(path)

    card.clear()

    assert not card.findChild(ChartCanvas).is_showing_chart()
    assert card._status.text() == "No report chosen yet."


def test_unreadable_report_is_handled_without_crashing(qapp, theme, tmp_path: Path):
    path = tmp_path / "missing.json"
    card = RSquaredCard(theme)

    card.load_report(path)

    canvas = card.findChild(ChartCanvas)
    assert not canvas.is_showing_chart()


def test_empty_test_pairs_shows_no_chart(qapp, theme, tmp_path: Path):
    path = tmp_path / "report.json"
    _write_report(path, [])
    card = RSquaredCard(theme)

    card.load_report(path)

    canvas = card.findChild(ChartCanvas)
    assert not canvas.is_showing_chart()
    assert "no test pairs" in card._status.text()


class _RaisingViewModel:
    def load(self, report_path: Path):
        raise RuntimeError("boom")


def test_an_unexpected_exception_is_reported_without_crashing(qapp, theme, tmp_path: Path):
    card = RSquaredCard(theme, _RaisingViewModel())

    card.load_report(tmp_path / "whatever.json")

    canvas = card.findChild(ChartCanvas)
    assert not canvas.is_showing_chart()
    assert "boom" in card._status.text()
