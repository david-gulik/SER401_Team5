from __future__ import annotations

from GAVEL.app.dtos.disagreement_category import DisagreementCategory
from GAVEL.app.usecases.classify_criterion_disagreement import classify_disagreement


def test_human_awarding_fewer_points_is_stricter() -> None:
    assert (
        classify_disagreement(human_points=1.0, proxy_points=2.0) == DisagreementCategory.STRICTER
    )


def test_human_awarding_more_points_is_lenient() -> None:
    assert classify_disagreement(human_points=2.0, proxy_points=1.0) == DisagreementCategory.LENIENT


def test_equal_points_is_exact() -> None:
    assert classify_disagreement(human_points=2.0, proxy_points=2.0) == DisagreementCategory.EXACT


def test_points_within_tolerance_is_exact() -> None:
    assert (
        classify_disagreement(human_points=2.0, proxy_points=2.00005) == DisagreementCategory.EXACT
    )


def test_points_outside_tolerance_is_not_exact() -> None:
    assert classify_disagreement(human_points=2.0, proxy_points=2.1) != DisagreementCategory.EXACT


def test_zero_points_both_sides_is_exact() -> None:
    assert classify_disagreement(human_points=0.0, proxy_points=0.0) == DisagreementCategory.EXACT
