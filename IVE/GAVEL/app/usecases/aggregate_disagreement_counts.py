from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from GAVEL.app.dtos.disagreement_category import DisagreementCategory
from GAVEL.app.usecases.classify_criterion_disagreement import classify_disagreement


@dataclass(frozen=True)
class CriterionScorePair:
    """One student's human and proxy points for one rubric criterion."""

    criterion: str
    human_points: float
    proxy_points: float


@dataclass(frozen=True)
class HeatMapCell:
    """How many students fell into one (criterion, disagreement category) cell."""

    criterion: str
    category: DisagreementCategory
    count: int


def aggregate_disagreement_counts(pairs: Sequence[CriterionScorePair]) -> tuple[HeatMapCell, ...]:
    """Classifies each pair and counts students per (criterion, category) cell.

    Criteria appear in first-seen order; within a criterion, cells appear in
    DisagreementCategory's declaration order. A (criterion, category)
    combination with no students is left out rather than appearing with a
    count of 0.
    """
    counts: dict[tuple[str, DisagreementCategory], int] = {}
    criteria_order: list[str] = []
    for pair in pairs:
        if pair.criterion not in criteria_order:
            criteria_order.append(pair.criterion)
        category = classify_disagreement(pair.human_points, pair.proxy_points)
        key = (pair.criterion, category)
        counts[key] = counts.get(key, 0) + 1

    return tuple(
        HeatMapCell(criterion=criterion, category=category, count=counts[(criterion, category)])
        for criterion in criteria_order
        for category in DisagreementCategory
        if (criterion, category) in counts
    )
