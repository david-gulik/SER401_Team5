from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class SignedErrorBin:
    lower: float
    upper: float
    count: int


def bin_signed_errors(
    values: Sequence[float], bin_width: float = 1.0
) -> tuple[SignedErrorBin, ...]:
    """Groups values into consecutive bins of equal width.

    Each bin includes its lower edge and excludes its upper edge. Bins run from
    the bin containing the smallest value to the bin containing the largest and
    empty bins between them are kept so that the counts form a continuous range.
    """
    if bin_width <= 0:
        raise ValueError("bin_width must be greater than zero.")
    if not values:
        return ()

    first_index = math.floor(min(values) / bin_width)
    last_index = math.floor(max(values) / bin_width)

    counts = [0] * (last_index - first_index + 1)
    for value in values:
        counts[math.floor(value / bin_width) - first_index] += 1

    return tuple(
        SignedErrorBin(
            lower=(first_index + offset) * bin_width,
            upper=(first_index + offset + 1) * bin_width,
            count=count,
        )
        for offset, count in enumerate(counts)
    )
