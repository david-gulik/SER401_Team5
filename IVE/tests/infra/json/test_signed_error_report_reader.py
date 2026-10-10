from __future__ import annotations

import json
from pathlib import Path

from GAVEL.infra.json.signed_error_report_reader import read_signed_errors


def _report(rows: list[dict]) -> dict:
    return {"rows": rows, "unmatched_submissions": [], "failed_submissions": []}


def test_returns_the_signed_error_of_each_row_in_order(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(
            _report(
                [
                    {
                        "student_identifier": "a",
                        "human_score": 4.0,
                        "proxy_score": 5.0,
                        "signed_error": -1.0,
                    },
                    {
                        "student_identifier": "b",
                        "human_score": 3.0,
                        "proxy_score": 1.5,
                        "signed_error": 1.5,
                    },
                ]
            )
        ),
        encoding="utf-8",
    )

    assert read_signed_errors(path) == (-1.0, 1.5)


def test_student_identifiers_are_not_returned(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(
            _report(
                [
                    {
                        "student_identifier": "aanon1234",
                        "human_score": 4.0,
                        "proxy_score": 4.0,
                        "signed_error": 0.0,
                    }
                ]
            )
        ),
        encoding="utf-8",
    )

    values = read_signed_errors(path)

    assert values == (0.0,)
    assert all(isinstance(value, float) for value in values)


def test_an_empty_report_returns_no_values(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_report([])), encoding="utf-8")

    assert read_signed_errors(path) == ()
