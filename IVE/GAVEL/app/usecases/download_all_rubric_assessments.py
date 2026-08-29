from __future__ import annotations

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
    error: str | None


@dataclass(frozen=True)
class DownloadAllRubricAssessmentsResult:
    outcomes: tuple[RubricAssessmentDownloadOutcome, ...]

    @property
    def successes(self) -> tuple[RubricAssessmentDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.error is None)

    @property
    def failures(self) -> tuple[RubricAssessmentDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.error is not None)


class DownloadAllRubricAssessmentsUseCase:
    """Downloads a rubric assessment file for every assignment in a course.

    Used by the "Download All" workflow, which previously downloaded a
    rubric assessment for at most one hard-coded assignment regardless of
    how many assignments the course actually had (SCRUM-223). Each
    assignment is attempted independently: one assignment failing does not
    stop the others from being downloaded.
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
                outcomes.append(
                    RubricAssessmentDownloadOutcome(
                        assignment_id=assignment.id,
                        assignment_name=assignment.name,
                        saved_path=result.saved_path,
                        error=None,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                outcomes.append(
                    RubricAssessmentDownloadOutcome(
                        assignment_id=assignment.id,
                        assignment_name=assignment.name,
                        saved_path=None,
                        error=str(exc),
                    )
                )

        return DownloadAllRubricAssessmentsResult(outcomes=tuple(outcomes))
