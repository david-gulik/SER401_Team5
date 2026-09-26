from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProxyGradeResult:
    """A proxy score: an autograder's test results mapped onto a human rubric's point scale.

    criterion_scores holds one point value per rubric criterion, in rubric
    order. total_score is their sum, comparable to a human grader's total
    for the same assignment.
    """

    criterion_scores: tuple[float, ...]
    total_score: float
