"""The JSON shape of rubric files, in one place.

The download use cases write with the ``*_to_*`` functions and the readers
load with the ``*_from_*`` functions, so the two cannot drift. The shape is
the one ``DownloadRubricAssessmentUseCase`` has always written, so files
downloaded before the workspace layout still load.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from GAVEL.app.dtos.rubric_assessment import RubricAssessment, RubricCriterionScore
from GAVEL.app.dtos.rubric_definition import (
    RubricCriterionDefinition,
    RubricDefinition,
    RubricRating,
)


def assessment_to_dict(assessment: RubricAssessment) -> dict[str, Any]:
    return {
        "student_id": assessment.student_id,
        "submission_id": assessment.submission_id,
        "criteria": [
            {
                "criterion_id": c.criterion_id,
                "points": c.points,
                "comments": c.comments,
            }
            for c in assessment.criteria
        ],
    }


def assessment_from_dict(data: dict[str, Any]) -> RubricAssessment:
    return RubricAssessment(
        student_id=int(data["student_id"]),
        submission_id=int(data["submission_id"]),
        criteria=tuple(
            RubricCriterionScore(
                criterion_id=str(c["criterion_id"]),
                points=None if c.get("points") is None else float(c["points"]),
                comments=str(c.get("comments") or ""),
            )
            for c in data.get("criteria", [])
        ),
    )


def assessments_to_json(assessments: Iterable[RubricAssessment]) -> str:
    return json.dumps([assessment_to_dict(a) for a in assessments], indent=2)


def assessments_from_json(text: str) -> tuple[RubricAssessment, ...]:
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("rubric assessments file must contain a JSON array")
    return tuple(assessment_from_dict(item) for item in data)


def definition_to_dict(definition: RubricDefinition) -> dict[str, Any]:
    return {
        "rubric_id": definition.rubric_id,
        "title": definition.title,
        "points_possible": definition.points_possible,
        "free_form_criterion_comments": definition.free_form_criterion_comments,
        "criteria": [
            {
                "id": c.id,
                "description": c.description,
                "long_description": c.long_description,
                "points": c.points,
                "ratings": [
                    {
                        "id": r.id,
                        "description": r.description,
                        "long_description": r.long_description,
                        "points": r.points,
                    }
                    for r in c.ratings
                ],
            }
            for c in definition.criteria
        ],
    }


def definition_from_dict(data: dict[str, Any]) -> RubricDefinition:
    return RubricDefinition(
        rubric_id=str(data["rubric_id"]),
        title=str(data.get("title") or ""),
        points_possible=_optional_float(data.get("points_possible")),
        free_form_criterion_comments=bool(data.get("free_form_criterion_comments", False)),
        criteria=tuple(
            RubricCriterionDefinition(
                id=str(c["id"]),
                description=str(c.get("description") or ""),
                long_description=str(c.get("long_description") or ""),
                points=_optional_float(c.get("points")),
                ratings=tuple(
                    RubricRating(
                        id=str(r["id"]),
                        description=str(r.get("description") or ""),
                        long_description=str(r.get("long_description") or ""),
                        points=_optional_float(r.get("points")),
                    )
                    for r in c.get("ratings", [])
                ),
            )
            for c in data.get("criteria", [])
        ),
    )


def definition_to_json(definition: RubricDefinition) -> str:
    return json.dumps(definition_to_dict(definition), indent=2)


def definition_from_json(text: str) -> RubricDefinition:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("rubric definition file must contain a JSON object")
    return definition_from_dict(data)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
