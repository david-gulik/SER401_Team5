from __future__ import annotations

import pytest

from GAVEL.app.usecases.compute_r_squared import compute_r_squared


def test_mismatched_lengths_are_rejected() -> None:
    with pytest.raises(ValueError):
        compute_r_squared([1.0, 2.0], [1.0])


def test_fewer_than_two_points_is_rejected() -> None:
    with pytest.raises(ValueError):
        compute_r_squared([1.0], [1.0])
    with pytest.raises(ValueError):
        compute_r_squared([], [])


def test_a_constant_series_has_no_defined_correlation() -> None:
    with pytest.raises(ValueError):
        compute_r_squared([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])


def test_a_perfect_positive_line_scores_one() -> None:
    assert compute_r_squared([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0]) == pytest.approx(1.0)


def test_a_perfect_negative_line_also_scores_one() -> None:
    # r-squared cannot distinguish direction, only how tightly the points fit a line.
    assert compute_r_squared([1.0, 2.0, 3.0, 4.0], [8.0, 6.0, 4.0, 2.0]) == pytest.approx(1.0)


def test_a_series_with_no_linear_relationship_scores_zero() -> None:
    assert compute_r_squared([1.0, 2.0, 3.0, 4.0], [3.0, 1.0, 4.0, 2.0]) == pytest.approx(0.0)


def test_does_not_depend_on_argument_order() -> None:
    xs, ys = [1.0, 2.0, 4.0, 5.0], [2.0, 1.0, 5.0, 7.0]

    assert compute_r_squared(xs, ys) == pytest.approx(compute_r_squared(ys, xs))
