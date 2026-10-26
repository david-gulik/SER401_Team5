from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.usecases.compute_mann_whitney_u import MannWhitneyUResult, compute_mann_whitney_u
from GAVEL.app.usecases.group_score_distributions import (
    GroupScoreDistribution,
    group_score_distributions,
)
from GAVEL.infra.json.heat_map_report_reader import read_criterion_score_pairs


@dataclass(frozen=True)
class ScoreDistributionData:
    report_label: str
    groups: tuple[GroupScoreDistribution, ...]
    # significance[i] is the Mann-Whitney U test for groups[i]'s human vs
    # proxy points, so the two tuples stay paired by index.
    significance: tuple[MannWhitneyUResult, ...]


class ScoreDistributionViewModel:
    def load(self, report_path: Path) -> ScoreDistributionData:
        pairs = read_criterion_score_pairs(report_path)
        groups = group_score_distributions(pairs)
        significance = tuple(
            compute_mann_whitney_u(group.human_points, group.proxy_points) for group in groups
        )
        return ScoreDistributionData(
            report_label=report_path.stem, groups=groups, significance=significance
        )
