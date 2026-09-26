from __future__ import annotations

import json
from pathlib import Path

from GAVEL.app.dtos.rubric_assessment import (
    RubricAssessment,
    RubricCriterionScore,
)


class RubricAssessmentJSONReader:
    def read(self, path: Path) -> list[RubricAssessment]:
        data = json.loads(path.read_text(encoding="utf-8"))

        return [
            RubricAssessment(
                student_id=int(entry["student_id"]),
                submission_id=int(entry["submission_id"]),
                criteria=tuple(
                    RubricCriterionScore(
                        criterion_id=criterion["criterion_id"],
                        points=criterion["points"],
                        comments=criterion["comments"],
                    )
                    for criterion in entry["criteria"]
                ),
            )
            for entry in data
        ]
