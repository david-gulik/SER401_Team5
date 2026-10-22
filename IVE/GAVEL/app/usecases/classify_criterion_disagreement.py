from __future__ import annotations

import math

from GAVEL.app.dtos.disagreement_category import DisagreementCategory

_TOLERANCE = 0.0001


def classify_disagreement(human_points: float, proxy_points: float) -> DisagreementCategory:
    """Categorizes how a human grader's criterion score compares to the proxy's.

    Stricter: the human awarded fewer points than the proxy. Lenient: the
    human awarded more. Exact: the two agree, within floating-point
    tolerance.
    """
    if math.isclose(human_points, proxy_points, abs_tol=_TOLERANCE):
        return DisagreementCategory.EXACT
    if human_points < proxy_points:
        return DisagreementCategory.STRICTER
    return DisagreementCategory.LENIENT
