from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RubricRating:
    id: str
    description: str
    long_description: str
    points: float | None


@dataclass(frozen=True)
class RubricCriterionDefinition:
    id: str
    description: str
    long_description: str
    points: float | None
    ratings: tuple[RubricRating, ...]


@dataclass(frozen=True)
class RubricDefinition:
    rubric_id: str
    title: str
    points_possible: float | None
    free_form_criterion_comments: bool
    criteria: tuple[RubricCriterionDefinition, ...]
