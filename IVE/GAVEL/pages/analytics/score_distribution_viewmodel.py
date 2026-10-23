from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.usecases.group_score_distributions import (
    GroupScoreDistribution,
    group_score_distributions,
)
from GAVEL.infra.json.heat_map_report_reader import read_criterion_score_pairs


@dataclass(frozen=True)
class ScoreDistributionData:
    report_label: str
    groups: tuple[GroupScoreDistribution, ...]


class ScoreDistributionViewModel:
    def load(self, report_path: Path) -> ScoreDistributionData:
        pairs = read_criterion_score_pairs(report_path)
        groups = group_score_distributions(pairs)
        return ScoreDistributionData(report_label=report_path.stem, groups=groups)
