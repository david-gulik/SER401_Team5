from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from GAVEL.app.usecases.aggregate_disagreement_counts import CriterionScorePair
from GAVEL.app.usecases.derive_criterion_group import derive_criterion_group


@dataclass(frozen=True)
class GroupScoreDistribution:
    """Every student's human and proxy points for one group of criteria, pooled.

    human_points[i] and proxy_points[i] come from the same (student, criterion)
    pair, so the two sequences stay paired by index.
    """

    group: str
    human_points: tuple[float, ...]
    proxy_points: tuple[float, ...]


def group_score_distributions(
    pairs: Sequence[CriterionScorePair],
) -> tuple[GroupScoreDistribution, ...]:
    """Pools each criterion's human and proxy points into its larger-requirement group.

    Groups come from derive_criterion_group, so criteria sharing a "::" prefix
    (as in "course_insert::memory" and "course_insert") are compared as a
    unit rather than only by individual criterion. Groups appear in
    first-seen order.
    """
    human_by_group: dict[str, list[float]] = {}
    proxy_by_group: dict[str, list[float]] = {}
    group_order: list[str] = []
    for pair in pairs:
        group = derive_criterion_group(pair.criterion)
        if group not in human_by_group:
            human_by_group[group] = []
            proxy_by_group[group] = []
            group_order.append(group)
        human_by_group[group].append(pair.human_points)
        proxy_by_group[group].append(pair.proxy_points)

    return tuple(
        GroupScoreDistribution(
            group=group,
            human_points=tuple(human_by_group[group]),
            proxy_points=tuple(proxy_by_group[group]),
        )
        for group in group_order
    )
