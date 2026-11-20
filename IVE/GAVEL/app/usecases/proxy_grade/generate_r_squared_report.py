"""Computes and writes a report of two independent r-squared checks for autograder
test redundancy and a programming score against another assessment column.

Note: tested with fixtures and a synthetic demo course only and not yet
against real course data. The real course data available so far is not
enough to exercise both checks together.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.gradescope import GradescopeSubmission
from GAVEL.app.usecases.compute_cross_assessment_correlation import (
    compute_cross_assessment_correlation,
)
from GAVEL.app.usecases.compute_test_redundancy import PairRedundancy, compute_test_redundancy


@dataclass(frozen=True)
class CrossAssessmentResult:
    column_a: str
    column_b: str
    r_squared: float


@dataclass(frozen=True)
class GenerateRSquaredReportResult:
    test_pairs: tuple[PairRedundancy, ...]
    cross_assessment: CrossAssessmentResult


def compute_r_squared_report(
    submissions: Sequence[GradescopeSubmission],
    gradebook: CanvasGradebook,
    assessment_column_a: str,
    assessment_column_b: str,
) -> GenerateRSquaredReportResult:
    """Runs both r-squared checks against already-loaded data.
    Raises ValueError if the submissions don't share one test suite or either assessment column is missing or
    has too little data to compare. Neither check depends on the other.
    """
    test_pairs = compute_test_redundancy(submissions)
    cross_assessment_r_squared = compute_cross_assessment_correlation(
        gradebook, assessment_column_a, assessment_column_b
    )
    return GenerateRSquaredReportResult(
        test_pairs=test_pairs,
        cross_assessment=CrossAssessmentResult(
            column_a=assessment_column_a,
            column_b=assessment_column_b,
            r_squared=cross_assessment_r_squared,
        ),
    )


def write_r_squared_report(result: GenerateRSquaredReportResult, output_path: Path) -> None:
    """Writes a result to disk in the r-squared report's JSON format."""
    payload = {
        "test_pairs": [
            {"test_a": pair.test_a, "test_b": pair.test_b, "r_squared": pair.r_squared}
            for pair in result.test_pairs
        ],
        "cross_assessment": {
            "column_a": result.cross_assessment.column_a,
            "column_b": result.cross_assessment.column_b,
            "r_squared": result.cross_assessment.r_squared,
        },
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
