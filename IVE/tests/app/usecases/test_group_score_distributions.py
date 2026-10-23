from __future__ import annotations

from GAVEL.app.usecases.aggregate_disagreement_counts import CriterionScorePair
from GAVEL.app.usecases.group_score_distributions import (
    GroupScoreDistribution,
    group_score_distributions,
)


def test_empty_input_produces_no_groups() -> None:
    assert group_score_distributions([]) == ()


def test_a_criterion_with_no_separator_is_its_own_group() -> None:
    pairs = [CriterionScorePair("schedule_print", human_points=2.0, proxy_points=1.0)]

    groups = group_score_distributions(pairs)

    assert groups == (
        GroupScoreDistribution("schedule_print", human_points=(2.0,), proxy_points=(1.0,)),
    )


def test_criteria_sharing_a_prefix_pool_into_one_group() -> None:
    pairs = [
        CriterionScorePair("course_insert", human_points=7.0, proxy_points=5.0),
        CriterionScorePair("course_insert::memory", human_points=2.0, proxy_points=1.0),
    ]

    groups = group_score_distributions(pairs)

    assert groups == (
        GroupScoreDistribution("course_insert", human_points=(7.0, 2.0), proxy_points=(5.0, 1.0)),
    )


def test_human_and_proxy_points_stay_paired_by_index() -> None:
    pairs = [
        CriterionScorePair("main menu", human_points=1.0, proxy_points=2.0),
        CriterionScorePair("main menu", human_points=0.0, proxy_points=1.0),
    ]

    groups = group_score_distributions(pairs)

    assert groups[0].human_points == (1.0, 0.0)
    assert groups[0].proxy_points == (2.0, 1.0)


def test_groups_appear_in_first_seen_order() -> None:
    pairs = [
        CriterionScorePair("memory leaks", human_points=1.0, proxy_points=1.0),
        CriterionScorePair("main menu", human_points=1.0, proxy_points=1.0),
    ]

    groups = group_score_distributions(pairs)

    assert [g.group for g in groups] == ["memory leaks", "main menu"]
