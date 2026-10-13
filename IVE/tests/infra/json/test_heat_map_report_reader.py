from __future__ import annotations

import json
from pathlib import Path

import pytest

from GAVEL.app.usecases.aggregate_disagreement_counts import CriterionScorePair
from GAVEL.infra.json.heat_map_report_reader import read_criterion_score_pairs


def _write_report(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")


def test_reads_rows_in_order(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(
        path,
        [
            {"criterion": "main menu", "human_points": 1.0, "proxy_points": 2.0},
            {"criterion": "memory leaks", "human_points": 2.0, "proxy_points": 2.0},
        ],
    )

    pairs = read_criterion_score_pairs(path)

    assert pairs == (
        CriterionScorePair("main menu", human_points=1.0, proxy_points=2.0),
        CriterionScorePair("memory leaks", human_points=2.0, proxy_points=2.0),
    )


def test_student_identifiers_are_not_returned(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(
        path,
        [
            {
                "student_identifier": "anon_01",
                "criterion": "main menu",
                "human_points": 1.0,
                "proxy_points": 2.0,
            }
        ],
    )

    pairs = read_criterion_score_pairs(path)

    assert pairs == (CriterionScorePair("main menu", human_points=1.0, proxy_points=2.0),)
    assert not hasattr(pairs[0], "student_identifier")


def test_empty_report_gives_empty_tuple(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(path, [])

    assert read_criterion_score_pairs(path) == ()


def test_a_signed_error_report_raises_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "student_identifier": "a",
                        "human_score": 4.0,
                        "proxy_score": 5.0,
                        "signed_error": -1.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not a heat map report"):
        read_criterion_score_pairs(path)


def test_a_file_with_no_rows_raises_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"not_rows": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="not a report file"):
        read_criterion_score_pairs(path)
