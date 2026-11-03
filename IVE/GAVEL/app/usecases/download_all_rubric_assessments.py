from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.progress import ProgressCallback, report
from GAVEL.app.usecases.download_rubric_assessment import (
    DownloadRubricAssessmentRequest,
    DownloadRubricAssessmentUseCase,
)
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.recording import ArtifactExistsError
from GAVEL.infra.json.rubric_json import assessments_from_json

log = logging.getLogger(__name__)

PROGRESS_LABEL = "Downloading rubric assessments"


@dataclass(frozen=True)
class DownloadAllRubricAssessmentsRequest:
    course_id: int
    folder: CourseFolder
    overwrite: bool = False


@dataclass(frozen=True)
class RubricAssessmentDownloadOutcome:
    assignment_id: int
    assignment_name: str
    saved_path: Path | None
    assessment_count: int | None
    has_rubric: bool | None
    error: str | None
    already_downloaded: bool = False

    @property
    def status(self) -> str:
        if self.already_downloaded:
            return "already_downloaded"
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
    def already_downloaded(self) -> tuple[RubricAssessmentDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "already_downloaded")

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
    than "succeeded" — determined upfront from CanvasAssignment.has_rubric
    (SCRUM-220), which list_assignments sets from the assignment DTO
    itself, not from attempting a download and interpreting the result.
    A skipped assignment is never fetched or written: no rubric_assessment
    file is produced for it at all. An assignment that has a rubric but
    hasn't been graded yet still counts as succeeded (verified via
    DownloadRubricAssessmentResult.definition_saved_path as a safety net,
    in case rubric presence changed between the list call and this one).

    An assignment whose files are already in the course folder is reported
    as "already_downloaded" and left alone; delete the course folder to
    refresh it.

    ``on_progress`` hears once the assignment list is known and again as each
    assignment finishes, whatever its outcome.
    """

    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(
        self,
        request: DownloadAllRubricAssessmentsRequest,
        on_progress: ProgressCallback | None = None,
    ) -> DownloadAllRubricAssessmentsResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        log.info("Listing assignments for course %s", request.course_id)
        assignments = self._canvas_client.list_assignments(request.course_id)
        total = len(assignments)
        with_rubric = sum(1 for a in assignments if a.has_rubric)
        log.info(
            "Found %d assignment(s) for course %s, %d with a rubric",
            total,
            request.course_id,
            with_rubric,
        )
        report(on_progress, PROGRESS_LABEL, 0, total)
        rubric_use_case = DownloadRubricAssessmentUseCase(self._canvas_client)

        outcomes = []
        for index, assignment in enumerate(assignments, start=1):
            log.info(
                "Assignment %d of %d: '%s' (id %s)", index, total, assignment.name, assignment.id
            )
            outcome = self._download_one(rubric_use_case, request, assignment)
            outcomes.append(outcome)
            _log_outcome(outcome, index, total)
            report(on_progress, PROGRESS_LABEL, index, total, assignment.name)

        result = DownloadAllRubricAssessmentsResult(outcomes=tuple(outcomes))
        log.info(
            "Rubric assessments for course %s done: %d saved, %d already downloaded, "
            "%d skipped, %d failed",
            request.course_id,
            len(result.succeeded),
            len(result.already_downloaded),
            len(result.skipped),
            len(result.failed),
        )
        return result

    @staticmethod
    def _download_one(
        rubric_use_case: DownloadRubricAssessmentUseCase,
        request: DownloadAllRubricAssessmentsRequest,
        assignment: CanvasAssignment,
    ) -> RubricAssessmentDownloadOutcome:
        if not assignment.has_rubric:
            return RubricAssessmentDownloadOutcome(
                assignment_id=assignment.id,
                assignment_name=assignment.name,
                saved_path=None,
                assessment_count=None,
                has_rubric=False,
                error=None,
            )

        try:
            result = rubric_use_case.execute(
                DownloadRubricAssessmentRequest(
                    course_id=request.course_id,
                    assignment=assignment,
                    folder=request.folder,
                    overwrite=request.overwrite,
                )
            )
        except ArtifactExistsError as exc:
            return RubricAssessmentDownloadOutcome(
                assignment_id=assignment.id,
                assignment_name=assignment.name,
                saved_path=exc.target,
                assessment_count=None,
                has_rubric=None,
                error=None,
                already_downloaded=True,
            )
        except Exception as exc:  # noqa: BLE001
            return RubricAssessmentDownloadOutcome(
                assignment_id=assignment.id,
                assignment_name=assignment.name,
                saved_path=None,
                assessment_count=None,
                has_rubric=None,
                error=str(exc),
            )

        count = len(assessments_from_json(result.saved_path.read_text(encoding="utf-8")))
        return RubricAssessmentDownloadOutcome(
            assignment_id=assignment.id,
            assignment_name=assignment.name,
            saved_path=result.saved_path,
            assessment_count=count,
            has_rubric=result.definition_saved_path is not None,
            error=None,
        )


def _log_outcome(outcome: RubricAssessmentDownloadOutcome, index: int, total: int) -> None:
    prefix = f"Assignment {index} of {total} '{outcome.assignment_name}'"
    if outcome.status == "succeeded":
        log.info(
            "%s: %s assessment(s) saved to %s", prefix, outcome.assessment_count, outcome.saved_path
        )
    elif outcome.status == "already_downloaded":
        log.info("%s: already downloaded at %s", prefix, outcome.saved_path)
    elif outcome.status == "skipped":
        log.info("%s: skipped, no rubric attached", prefix)
    else:
        log.error("%s: failed, %s", prefix, outcome.error)
