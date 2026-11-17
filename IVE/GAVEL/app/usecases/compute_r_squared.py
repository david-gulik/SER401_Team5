from __future__ import annotations

from collections.abc import Sequence


def compute_r_squared(xs: Sequence[float], ys: Sequence[float]) -> float:
    """The coefficient of determination (r-squared) between two paired series.

    Computed as the square of the Pearson correlation coefficient. Values
    are paired by position, so xs[i] and ys[i] must be the same observation.

    Raises ValueError if the series have different lengths, fewer than two
    points each, or either series is constant (its variance is zero, which
    makes the correlation undefined rather than any particular number).
    """
    if len(xs) != len(ys):
        raise ValueError("xs and ys must be the same length.")
    if len(xs) < 2:
        raise ValueError("At least two paired points are required.")

    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)

    deviations_x = [x - mean_x for x in xs]
    deviations_y = [y - mean_y for y in ys]

    covariance = sum(dx * dy for dx, dy in zip(deviations_x, deviations_y, strict=True))
    variance_x = sum(dx * dx for dx in deviations_x)
    variance_y = sum(dy * dy for dy in deviations_y)

    if variance_x == 0 or variance_y == 0:
        raise ValueError("A constant series has no defined correlation.")

    correlation = covariance / (variance_x * variance_y) ** 0.5
    return correlation**2
