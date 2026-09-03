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
    has_rubric: bool | None
    error: str | None

    @property
    def status(self) -> str:
        if self.error is not None:
            return "failed"
        if self.has_rubric is False:
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

    An assignment with no rubric attached is reported as "skipped" rather
    than "succeeded", determined from whether fetch_rubric_definition
    actually found a rubric (via DownloadRubricAssessmentResult's
    definition_saved_path) rather than from an empty assessment list —
    an assignment that has a rubric but hasn't been graded yet still
    counts as succeeded.
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
                        has_rubric=result.definition_saved_path is not None,
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
                        has_rubric=None,
                        error=str(exc),
                    )
                )

        return DownloadAllRubricAssessmentsResult(outcomes=tuple(outcomes))
