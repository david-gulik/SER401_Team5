from __future__ import annotations

import json
from pathlib import Path

from GAVEL.pages.analytics.signed_error_histogram_viewmodel import (
    SignedErrorHistogramViewModel,
)


def _write_report(path: Path, signed_errors: list[float]) -> None:
    rows = [
        {"student_identifier": f"s{i}", "human_score": 0.0, "proxy_score": 0.0, "signed_error": v}
        for i, v in enumerate(signed_errors)
    ]
    path.write_text(
        json.dumps({"rows": rows, "unmatched_submissions": [], "failed_submissions": []}),
        encoding="utf-8",
    )


def test_bins_the_report_s_signed_errors(tmp_path: Path) -> None:
    path = tmp_path / "ser334_m2.json"
    _write_report(path, [-1.0, 0.5, 0.5])

    data = SignedErrorHistogramViewModel().load(path)

    assert sum(b.count for b in data.bins) == 3


def test_the_module_label_comes_from_the_file_name(tmp_path: Path) -> None:
    path = tmp_path / "ser334_m2.json"
    _write_report(path, [0.0])

    data = SignedErrorHistogramViewModel().load(path)

    assert data.module_label == "ser334_m2"


def test_an_empty_report_produces_no_bins(tmp_path: Path) -> None:
    path = tmp_path / "ser334_m2.json"
    _write_report(path, [])

    data = SignedErrorHistogramViewModel().load(path)

    assert data.bins == ()


def test_a_custom_bin_width_is_passed_through(tmp_path: Path) -> None:
    path = tmp_path / "ser334_m2.json"
    _write_report(path, [0.1, 0.6])

    data = SignedErrorHistogramViewModel().load(path, bin_width=0.5)

    assert len(data.bins) == 2
