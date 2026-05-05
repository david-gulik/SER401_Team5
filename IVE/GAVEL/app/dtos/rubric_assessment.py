from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RubricCriterionScore:
    criterion_id: str
    points: float | None
    comments: str


@dataclass(frozen=True)
class RubricAssessment:
    student_id: int
    submission_id: int
    criteria: tuple[RubricCriterionScore, ...]
