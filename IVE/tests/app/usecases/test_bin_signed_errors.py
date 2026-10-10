from __future__ import annotations

import pytest

from GAVEL.app.usecases.bin_signed_errors import SignedErrorBin, bin_signed_errors


def test_no_values_gives_no_bins() -> None:
    assert bin_signed_errors([]) == ()


def test_a_single_value_falls_in_one_bin() -> None:
    assert bin_signed_errors([2.5]) == (SignedErrorBin(lower=2.0, upper=3.0, count=1),)


def test_a_value_on_a_lower_edge_goes_to_the_bin_above_it() -> None:
    bins = bin_signed_errors([2.0, 3.0])

    assert bins == (
        SignedErrorBin(lower=2.0, upper=3.0, count=1),
        SignedErrorBin(lower=3.0, upper=4.0, count=1),
    )


def test_negative_values_are_binned_below_zero() -> None:
    bins = bin_signed_errors([-1.5, -0.5, 0.5])

    assert [(b.lower, b.count) for b in bins] == [(-2.0, 1), (-1.0, 1), (0.0, 1)]


def test_empty_bins_between_values_are_kept() -> None:
    bins = bin_signed_errors([0.5, 3.5])

    assert [b.count for b in bins] == [1, 0, 0, 1]


def test_counts_add_up_to_the_number_of_values() -> None:
    values = [-3.2, -1.0, -0.1, 0.0, 0.4, 1.9, 2.0, 2.0, 5.7]

    bins = bin_signed_errors(values)

    assert sum(b.count for b in bins) == len(values)


def test_bins_are_contiguous_and_of_equal_width() -> None:
    bins = bin_signed_errors([-2.2, 4.1], bin_width=2.0)

    assert all(b.upper - b.lower == pytest.approx(2.0) for b in bins)
    assert all(left.upper == right.lower for left, right in zip(bins, bins[1:], strict=False))


def test_a_custom_bin_width_is_used() -> None:
    bins = bin_signed_errors([0.1, 0.6], bin_width=0.5)

    assert bins == (
        SignedErrorBin(lower=0.0, upper=0.5, count=1),
        SignedErrorBin(lower=0.5, upper=1.0, count=1),
    )


def test_a_bin_width_of_zero_or_less_is_rejected() -> None:
    with pytest.raises(ValueError):
        bin_signed_errors([1.0], bin_width=0)
