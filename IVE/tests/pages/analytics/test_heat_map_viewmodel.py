from __future__ import annotations

import json
from pathlib import Path

from GAVEL.app.dtos.disagreement_category import DisagreementCategory
from GAVEL.app.usecases.aggregate_disagreement_counts import HeatMapCell
from GAVEL.pages.analytics.heat_map_viewmodel import HeatMapViewModel


def _write_report(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")


def test_load_labels_the_data_from_the_report_filename(tmp_path: Path) -> None:
    path = tmp_path / "m2_heat_map.json"
    _write_report(path, [])

    data = HeatMapViewModel().load(path)

    assert data.report_label == "m2_heat_map"


def test_load_aggregates_the_report_s_rows(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(
        path,
        [
            {"criterion": "main menu", "human_points": 1.0, "proxy_points": 2.0},
            {"criterion": "main menu", "human_points": 2.0, "proxy_points": 2.0},
        ],
    )

    data = HeatMapViewModel().load(path)

    assert data.cells == (
        HeatMapCell("main menu", DisagreementCategory.STRICTER, 1),
        HeatMapCell("main menu", DisagreementCategory.EXACT, 1),
    )


def test_load_with_no_rows_gives_no_cells(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    _write_report(path, [])

    data = HeatMapViewModel().load(path)

    assert data.cells == ()
