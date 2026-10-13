from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.usecases.aggregate_disagreement_counts import (
    HeatMapCell,
    aggregate_disagreement_counts,
)
from GAVEL.infra.json.heat_map_report_reader import read_criterion_score_pairs


@dataclass(frozen=True)
class HeatMapData:
    report_label: str
    cells: tuple[HeatMapCell, ...]


class HeatMapViewModel:
    def load(self, report_path: Path) -> HeatMapData:
        pairs = read_criterion_score_pairs(report_path)
        cells = aggregate_disagreement_counts(pairs)
        return HeatMapData(report_label=report_path.stem, cells=cells)
