from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.download_rubric_assessment import (
    DownloadRubricAssessmentRequest,
    DownloadRubricAssessmentUseCase,
)


@dataclass(frozen=True)
class DownloadAllRubricAssessmentsRequest:
    course_id: int
    output_dir: Path


@dataclass(frozen=True)
class RubricAssessmentDownloadOutcome:
    assignment_id: int
    assignment_name: str
    saved_path: Path | None
    assessment_count: int | None
    error: str | None

    @property
    def status(self) -> str:
        if self.error is not None:
            return "failed"
        if self.assessment_count == 0:
            return "skipped"
        return "succeeded"


@dataclass(frozen=True)
class DownloadAllRubricAssessmentsResult:
    outcomes: tuple[RubricAssessmentDownloadOutcome, ...]

    @property
    def succeeded(self) -> tuple[RubricAssessmentDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "succeeded")

    @property
    def skipped(self) -> tuple[RubricAssessmentDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "skipped")

    @property
    def failed(self) -> tuple[RubricAssessmentDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "failed")


class DownloadAllRubricAssessmentsUseCase:
    """Downloads a rubric assessment file for every assignment in a course.

    Used by the "Download All" workflow, which previously downloaded a
    rubric assessment for at most one hard-coded assignment regardless of
    how many assignments the course actually had (SCRUM-223). Each
    assignment is attempted independently: one assignment failing does not
    stop the others from being downloaded.

    An assignment whose downloaded file has zero assessment entries is
    reported as "skipped" rather than "succeeded" — see the note on
    RubricAssessmentDownloadOutcome.status about what that does and doesn't
    mean yet.
    """

    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(
        self, request: DownloadAllRubricAssessmentsRequest
    ) -> DownloadAllRubricAssessmentsResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        assignments = self._canvas_client.list_assignments(request.course_id)
        rubric_use_case = DownloadRubricAssessmentUseCase(self._canvas_client)

        outcomes = []
        for assignment in assignments:
            try:
                result = rubric_use_case.execute(
                    DownloadRubricAssessmentRequest(
                        course_id=request.course_id,
                        assignment_id=assignment.id,
                        output_dir=request.output_dir,
                    )
                )
                assessments = json.loads(result.saved_path.read_text(encoding="utf-8"))
                outcomes.append(
                    RubricAssessmentDownloadOutcome(
                        assignment_id=assignment.id,
                        assignment_name=assignment.name,
                        saved_path=result.saved_path,
                        assessment_count=len(assessments),
                        error=None,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                outcomes.append(
                    RubricAssessmentDownloadOutcome(
                        assignment_id=assignment.id,
                        assignment_name=assignment.name,
                        saved_path=None,
                        assessment_count=None,
                        error=str(exc),
                    )
                )

        return DownloadAllRubricAssessmentsResult(outcomes=tuple(outcomes))
