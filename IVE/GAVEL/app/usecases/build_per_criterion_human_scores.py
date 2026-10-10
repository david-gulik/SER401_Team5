from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition


@dataclass(frozen=True)
class HumanCriterionScore:
    student_id: int
    criterion: str
    points: float | None
    points_possible: float | None


class UnknownRubricCriterionError(ValueError):
    """A rubric assessment refers to a criterion that the rubric definition does not contain."""

    def __init__(self, unknown: Sequence[str]) -> None:
        self.unknown = tuple(unknown)
        super().__init__(f"Rubric assessment refers to unknown criteria: {', '.join(self.unknown)}")


def build_per_criterion_human_scores(
    definition: RubricDefinition,
    assessments: Sequence[RubricAssessment],
) -> tuple[HumanCriterionScore, ...]:
    """Turns rubric assessments into one row per student per criterion.

    Criterion names and point values come from the rubric definition, matched to
    each assessment entry by criterion id. Rows follow the order of the rubric's
    criteria within each student. Assessments are expected to already carry the
    anonymized student id.
    """
    by_id = {criterion.id: criterion for criterion in definition.criteria}

    unknown = sorted(
        {
            score.criterion_id
            for assessment in assessments
            for score in assessment.criteria
            if score.criterion_id not in by_id
        }
    )
    if unknown:
        raise UnknownRubricCriterionError(unknown)

    rows: list[HumanCriterionScore] = []
    for assessment in assessments:
        scores_by_id = {score.criterion_id: score for score in assessment.criteria}
        for criterion in definition.criteria:
            score = scores_by_id.get(criterion.id)
            if score is None:
                continue
            rows.append(
                HumanCriterionScore(
                    student_id=assessment.student_id,
                    criterion=criterion.description,
                    points=score.points,
                    points_possible=criterion.points,
                )
            )
    return tuple(rows)
