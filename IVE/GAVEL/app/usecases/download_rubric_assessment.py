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

        message = f"Rubric assessment for course {request.course_id}, assignment {request.assignment_id} saved to {path}"
        return DownloadRubricAssessmentResult(saved_path=path, message=message)
