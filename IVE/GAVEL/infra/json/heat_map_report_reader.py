from __future__ import annotations

import json
from pathlib import Path

from GAVEL.app.usecases.aggregate_disagreement_counts import CriterionScorePair


def read_criterion_score_pairs(path: Path) -> tuple[CriterionScorePair, ...]:
    """Reads a heat map report's per-student-per-criterion score pairs.

    Each pair carries the anonymized student identifier that is saved in the file.
    A row with no identifier at all (e.g. a hand-written fixture) gets ""
    instead of raising.

    Note: tested with fixtures, but will not work against real data until
    anonymize_course_dataset.py writes an anonymized submission_metadata.yml
    into anonymized/. The anonymized data should be written to that location.

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
                student_identifier=str(row.get("student_identifier", "")),
            )
            for row in data["rows"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path.name} is not a heat map report ({exc}).") from exc
