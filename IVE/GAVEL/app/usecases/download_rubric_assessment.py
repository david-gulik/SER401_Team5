from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.canvas_client import CanvasClient


@dataclass(frozen=True)
class DownloadRubricAssessmentRequest:
    course_id: int
    assignment_id: int
    output_dir: Path


@dataclass(frozen=True)
class DownloadRubricAssessmentResult:
    saved_path: Path
    definition_saved_path: Path | None
    message: str


class DownloadRubricAssessmentUseCase:
    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(self, request: DownloadRubricAssessmentRequest) -> DownloadRubricAssessmentResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")
        if request.assignment_id <= 0:
            raise ValueError("assignment_id must be greater than zero")

        request.output_dir.mkdir(parents=True, exist_ok=True)

        assessments = self._canvas_client.fetch_rubric_assessments(
            request.course_id, request.assignment_id
        )

        payload = [
            {
                "student_id": a.student_id,
                "submission_id": a.submission_id,
                "criteria": [
                    {
                        "criterion_id": c.criterion_id,
                        "points": c.points,
                        "comments": c.comments,
                    }
                    for c in a.criteria
                ],
            }
            for a in assessments
        ]

        path = (
            request.output_dir
            / f"rubric_assessment_{request.course_id}_{request.assignment_id}.json"
        )
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        definition_path = self._save_rubric_definition(request)

        message = f"Rubric assessment for course {request.course_id}, assignment {request.assignment_id} saved to {path}"
        return DownloadRubricAssessmentResult(
            saved_path=path,
            definition_saved_path=definition_path,
            message=message,
        )

    def _save_rubric_definition(self, request: DownloadRubricAssessmentRequest) -> Path | None:
        definition = self._canvas_client.fetch_rubric_definition(
            request.course_id, request.assignment_id
        )
        if definition is None:
            return None

        payload = {
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

        path = (
            request.output_dir
            / f"rubric_definition_{request.course_id}_{request.assignment_id}.json"
        )
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
