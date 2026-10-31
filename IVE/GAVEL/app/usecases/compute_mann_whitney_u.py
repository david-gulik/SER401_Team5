from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class MannWhitneyUResult:
    u_statistic: float
    p_value: float


def _ranks_and_tie_sizes(values: Sequence[float]) -> tuple[list[float], list[int]]:
    """Ranks values ascending from 1, averaging ranks across tied values.

    Also returns the size of each group of tied values, needed to correct the
    test's variance for ties.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    tie_sizes: list[int] = []
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average_rank
        tie_sizes.append(j - i + 1)
        i = j + 1
    return ranks, tie_sizes


def compute_mann_whitney_u(
    group_a: Sequence[float], group_b: Sequence[float]
) -> MannWhitneyUResult:
    """The Mann-Whitney U test, testing whether group_a and group_b come from the
    same distribution.

    The p-value uses the normal approximation with a tie correction and a
    continuity correction, two-tailed, matching scipy.stats.mannwhitneyu's
    asymptotic method. When every value in both groups is tied, the variance
    is zero and this returns p_value=1.0 rather than scipy's NaN, since the
    groups are indistinguishable rather than the test being undefined.
    """
    if not group_a or not group_b:
        raise ValueError("Both groups must be non-empty.")

    n1, n2 = len(group_a), len(group_b)
    n = n1 + n2
    ranks, tie_sizes = _ranks_and_tie_sizes([*group_a, *group_b])
    rank_sum_a = sum(ranks[:n1])

    u1 = rank_sum_a - n1 * (n1 + 1) / 2
    u2 = n1 * n2 - u1
    u = min(u1, u2)

    mean_u = n1 * n2 / 2
    tie_term = sum(size**3 - size for size in tie_sizes)
    variance_u = n1 * n2 / 12 * ((n + 1) - tie_term / (n * (n - 1)))
    std_u = math.sqrt(variance_u)
    if std_u == 0:
        return MannWhitneyUResult(u_statistic=u, p_value=1.0)

    difference = u - mean_u
    continuity_correction = 0.5 if difference > 0 else (-0.5 if difference < 0 else 0.0)
    z = (difference - continuity_correction) / std_u
    p_value = math.erfc(abs(z) / math.sqrt(2))

    return MannWhitneyUResult(u_statistic=u, p_value=p_value)
