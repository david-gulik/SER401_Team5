from __future__ import annotations

import json
from pathlib import Path

from GAVEL.app.usecases.group_score_distributions import GroupScoreDistribution
from GAVEL.pages.analytics.score_distribution_viewmodel import ScoreDistributionViewModel


def _write_report(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")


def test_load_labels_the_data_from_the_report_filename(tmp_path: Path) -> None:
    path = tmp_path / "m2_heat_map.json"
    _write_report(path, [])

    data = ScoreDistributionViewModel().load(path)

    assert data.report_label == "m2_heat_map"


def test_load_groups_the_report_s_rows(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(
        path,
        [
            {"criterion": "course_insert", "human_points": 7.0, "proxy_points": 5.0},
            {"criterion": "course_insert::memory", "human_points": 2.0, "proxy_points": 1.0},
        ],
    )

    data = ScoreDistributionViewModel().load(path)

    assert data.groups == (
        GroupScoreDistribution("course_insert", human_points=(7.0, 2.0), proxy_points=(5.0, 1.0)),
    )


def test_load_with_no_rows_gives_no_groups(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(path, [])

    data = ScoreDistributionViewModel().load(path)

    assert data.groups == ()
