from __future__ import annotations

from enum import Enum


class DisagreementCategory(Enum):
    """Classification for how a human grader's per-criterion score compares to the proxy's."""

    STRICTER = "stricter"
    EXACT = "exact"
    LENIENT = "lenient"
