from __future__ import annotations

import json
from pathlib import Path

from GAVEL.pages.analytics.signed_error_histogram_viewmodel import SignedErrorHistogramViewModel
from GAVEL.pages.analytics.tabs import SignedErrorHistogramCard
from GAVEL.ui_components.chart_canvas import ChartCanvas


def _write_report(path: Path, signed_errors: list[float]) -> None:
    rows = [
        {"student_identifier": f"s{i}", "human_score": 0.0, "proxy_score": 0.0, "signed_error": v}
        for i, v in enumerate(signed_errors)
    ]
    path.write_text(
        json.dumps({"rows": rows, "unmatched_submissions": [], "failed_submissions": []}),
        encoding="utf-8",
    )


def test_starts_with_an_empty_placeholder_chart(qapp, theme):
    card = SignedErrorHistogramCard(theme)

    canvases = card.findChildren(ChartCanvas)

    assert len(canvases) == 1
    assert not canvases[0].is_showing_chart()


def test_loading_a_report_draws_the_chart(qapp, theme, tmp_path: Path):
    path = tmp_path / "ser334_m2.json"
    _write_report(path, [-1.0, 0.5, 0.5])
    card = SignedErrorHistogramCard(theme, SignedErrorHistogramViewModel())

    card.load_report(path)

    canvas = card.findChildren(ChartCanvas)[0]
    assert canvas.is_showing_chart()
    assert "ser334_m2" in card._status.text()


def test_an_unreadable_report_is_reported_without_crashing(qapp, theme, tmp_path: Path):
    path = tmp_path / "not_json.json"
    path.write_text("not valid json", encoding="utf-8")
    card = SignedErrorHistogramCard(theme, SignedErrorHistogramViewModel())

    card.load_report(path)

    canvas = card.findChildren(ChartCanvas)[0]
    assert not canvas.is_showing_chart()
    assert "not_json.json" in card._status.text()


def test_an_empty_report_shows_no_chart(qapp, theme, tmp_path: Path):
    path = tmp_path / "ser334_m2.json"
    _write_report(path, [])
    card = SignedErrorHistogramCard(theme, SignedErrorHistogramViewModel())

    card.load_report(path)

    canvas = card.findChildren(ChartCanvas)[0]
    assert not canvas.is_showing_chart()
