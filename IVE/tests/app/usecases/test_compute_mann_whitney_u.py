from __future__ import annotations

import pytest

from GAVEL.app.usecases.compute_mann_whitney_u import compute_mann_whitney_u


def test_an_empty_group_is_rejected() -> None:
    with pytest.raises(ValueError):
        compute_mann_whitney_u([], [1.0])
    with pytest.raises(ValueError):
        compute_mann_whitney_u([1.0], [])


def test_completely_separated_groups_have_a_small_p_value() -> None:
    # Matches scipy.stats.mannwhitneyu(method="asymptotic") on the same input.
    result = compute_mann_whitney_u([1, 2, 3, 4, 5], [6, 7, 8, 9, 10])

    assert result.u_statistic == 0.0
    assert result.p_value == pytest.approx(0.012185780355344813)


def test_overlapping_groups_have_a_larger_p_value() -> None:
    result = compute_mann_whitney_u([1, 2, 3, 4, 5], [3, 4, 5, 6, 7])

    assert result.u_statistic == 4.5
    assert result.p_value == pytest.approx(0.11384629800665805)


def test_ties_are_handled_with_a_variance_correction() -> None:
    result = compute_mann_whitney_u([2.1, 3.4, 1.0], [5.5, 6.6, 4.4, 7.7])

    assert result.u_statistic == 0.0
    assert result.p_value == pytest.approx(0.05182992721790968)


def test_identical_groups_score_the_maximum_p_value() -> None:
    result = compute_mann_whitney_u([1, 3, 5, 7, 9, 11], [2, 4, 6, 8, 10])

    assert result.u_statistic == 15.0
    assert result.p_value == pytest.approx(1.0)


def test_every_value_tied_gives_a_p_value_of_one_instead_of_undefined() -> None:
    result = compute_mann_whitney_u([5, 5, 5, 5], [5, 5, 5, 5])

    assert result.u_statistic == 8.0
    assert result.p_value == 1.0


def test_the_u_statistic_does_not_depend_on_argument_order() -> None:
    forward = compute_mann_whitney_u([1, 2, 3], [4, 5, 6, 7])
    backward = compute_mann_whitney_u([4, 5, 6, 7], [1, 2, 3])

    assert forward.u_statistic == backward.u_statistic
    assert forward.p_value == pytest.approx(backward.p_value)
