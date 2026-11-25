from __future__ import annotations

import json
from pathlib import Path

import pytest

from GAVEL.app.usecases.compute_test_redundancy import PairRedundancy
from GAVEL.app.usecases.proxy_grade.generate_r_squared_report import CrossAssessmentResult
from GAVEL.infra.json.r_squared_report_reader import read_r_squared_report


def _write_report(path: Path, test_pairs: list[dict], cross_assessment: dict) -> None:
    path.write_text(
        json.dumps({"test_pairs": test_pairs, "cross_assessment": cross_assessment}),
        encoding="utf-8",
    )


def test_reads_test_pairs_and_cross_assessment_in_order(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(
        path,
        [
            {"test_a": "A", "test_b": "B", "r_squared": 0.9},
            {"test_a": "A", "test_b": "C", "r_squared": 0.1},
        ],
        {"column_a": "Programming", "column_b": "Quiz", "r_squared": 0.5},
    )

    result = read_r_squared_report(path)

    assert result.test_pairs == (
        PairRedundancy("A", "B", 0.9),
        PairRedundancy("A", "C", 0.1),
    )
    assert result.cross_assessment == CrossAssessmentResult("Programming", "Quiz", 0.5)


def test_an_empty_test_pairs_list_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(path, [], {"column_a": "A", "column_b": "B", "r_squared": 1.0})

    result = read_r_squared_report(path)

    assert result.test_pairs == ()


def test_a_heat_map_report_raises_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(
            {"rows": [{"criterion": "main menu", "human_points": 1.0, "proxy_points": 2.0}]}
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not an r-squared report"):
        read_r_squared_report(path)


def test_a_file_whose_top_level_is_a_list_raises_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps([{"test_a": "A"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="not an r-squared report"):
        read_r_squared_report(path)


def test_a_malformed_test_pair_raises_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(
        path,
        [{"test_a": "A"}],  # missing test_b/r_squared
        {"column_a": "A", "column_b": "B", "r_squared": 1.0},
    )

    with pytest.raises(ValueError, match="not an r-squared report"):
        read_r_squared_report(path)
