from __future__ import annotations

import random
from dataclasses import dataclass

from GAVEL.app.dtos.rubric_assessment import RubricAssessment


@dataclass(frozen=True)
class AnonymizeRubricAssessmentRequest:
    assessments: tuple[RubricAssessment, ...]
    consented_ids: tuple[int, ...]
    id_map: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class AnonymizeRubricAssessmentResult:
    assessments: tuple[RubricAssessment, ...]
    skipped_count: int
    excluded_count: int


class AnonymizeRubricAssessmentUseCase:
    def execute(self, request: AnonymizeRubricAssessmentRequest) -> AnonymizeRubricAssessmentResult:
        """
        Filters and anonymizes a collection of RubricAssessment objects.
        """
        id_map = dict(request.id_map)
        consented = set(request.consented_ids)

        anonymized = []
        skipped_count = 0
        excluded_count = 0

        for assessment in request.assessments:
            if assessment.student_id not in id_map:
                skipped_count += 1
                continue

            if assessment.student_id not in consented:
                excluded_count += 1
                continue

            anonymous_id = id_map[assessment.student_id]

            anonymized.append(
                RubricAssessment(
                    student_id=anonymous_id,
                    submission_id=int("30000" + str(anonymous_id)),
                    criteria=assessment.criteria,
                )
            )

        random.shuffle(anonymized)

        return AnonymizeRubricAssessmentResult(
            assessments=tuple(anonymized),
            skipped_count=skipped_count,
            excluded_count=excluded_count,
        )
