from __future__ import annotations

from GAVEL.app.dtos.disagreement_category import DisagreementCategory
from GAVEL.app.usecases.aggregate_disagreement_counts import (
    CriterionScorePair,
    HeatMapCell,
    aggregate_disagreement_counts,
)


def test_empty_input_produces_no_cells() -> None:
    assert aggregate_disagreement_counts([]) == ()


def test_one_pair_produces_one_cell_with_count_one() -> None:
    pairs = [CriterionScorePair("main menu", human_points=1.0, proxy_points=2.0)]

    cells = aggregate_disagreement_counts(pairs)

    assert cells == (HeatMapCell("main menu", DisagreementCategory.STRICTER, 1),)


def test_multiple_students_in_the_same_cell_are_counted_together() -> None:
    pairs = [
        CriterionScorePair("main menu", human_points=1.0, proxy_points=2.0),
        CriterionScorePair("main menu", human_points=0.0, proxy_points=1.0),
        CriterionScorePair("main menu", human_points=2.0, proxy_points=2.0),
    ]

    cells = aggregate_disagreement_counts(pairs)

    assert cells == (
        HeatMapCell("main menu", DisagreementCategory.STRICTER, 2),
        HeatMapCell("main menu", DisagreementCategory.EXACT, 1),
    )


def test_criteria_appear_in_first_seen_order() -> None:
    pairs = [
        CriterionScorePair("memory leaks", human_points=1.0, proxy_points=1.0),
        CriterionScorePair("main menu", human_points=1.0, proxy_points=1.0),
    ]

    cells = aggregate_disagreement_counts(pairs)

    assert [cell.criterion for cell in cells] == ["memory leaks", "main menu"]


def test_cells_with_no_students_are_left_out() -> None:
    pairs = [CriterionScorePair("main menu", human_points=1.0, proxy_points=1.0)]

    cells = aggregate_disagreement_counts(pairs)

    assert cells == (HeatMapCell("main menu", DisagreementCategory.EXACT, 1),)
