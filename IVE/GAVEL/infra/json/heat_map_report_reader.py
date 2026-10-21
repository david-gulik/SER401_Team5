from __future__ import annotations

import json
from pathlib import Path

from GAVEL.app.usecases.aggregate_disagreement_counts import CriterionScorePair


def read_criterion_score_pairs(path: Path) -> tuple[CriterionScorePair, ...]:
    """Reads a heat map report's per-student-per-criterion score pairs.

    Only criterion, human_points, and proxy_points are read; any student
    identifier in the file is ignored, so the chart never carries one.

    Raises ValueError, naming the file, if it is not a heat map report (e.g.
    a signed-error report was chosen instead).
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise ValueError(f"{path.name} is not a report file (missing 'rows').")

    try:
        return tuple(
            CriterionScorePair(
                criterion=str(row["criterion"]),
                human_points=float(row["human_points"]),
                proxy_points=float(row["proxy_points"]),
            )
            for row in data["rows"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path.name} is not a heat map report ({exc}).") from exc
