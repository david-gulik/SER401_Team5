from __future__ import annotations

import json
from pathlib import Path

from GAVEL.app.usecases.compute_test_redundancy import PairRedundancy
from GAVEL.app.usecases.proxy_grade.generate_r_squared_report import (
    CrossAssessmentResult,
    GenerateRSquaredReportResult,
)


def read_r_squared_report(path: Path) -> GenerateRSquaredReportResult:
    """Reads an r-squared report's test-pair and cross-assessment results.
    Raises ValueError if it is not an r-squared report
    (if a heat map or signed-error report was chosen instead).
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("test_pairs"), list)
        or not isinstance(payload.get("cross_assessment"), dict)
    ):
        raise ValueError(f"{path.name} is not an r-squared report.")

    try:
        test_pairs = tuple(
            PairRedundancy(
                test_a=str(pair["test_a"]),
                test_b=str(pair["test_b"]),
                r_squared=float(pair["r_squared"]),
            )
            for pair in payload["test_pairs"]
        )
        cross_assessment_payload = payload["cross_assessment"]
        cross_assessment = CrossAssessmentResult(
            column_a=str(cross_assessment_payload["column_a"]),
            column_b=str(cross_assessment_payload["column_b"]),
            r_squared=float(cross_assessment_payload["r_squared"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path.name} is not an r-squared report ({exc}).") from exc

    return GenerateRSquaredReportResult(test_pairs=test_pairs, cross_assessment=cross_assessment)
