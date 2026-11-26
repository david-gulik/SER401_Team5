from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.progress import ProgressCallback, report
from GAVEL.app.usecases.download_assignment_submissions import (
    DownloadAssignmentSubmissionsRequest,
    DownloadAssignmentSubmissionsUseCase,
)
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.recording import ArtifactExistsError

log = logging.getLogger(__name__)

PROGRESS_LABEL = "Downloading assignment submissions"


def _accepts_file_uploads(assignment: CanvasAssignment) -> bool:
    return bool(assignment.submission_types and "online_upload" in assignment.submission_types)


@dataclass(frozen=True)
class DownloadAllAssignmentSubmissionsRequest:
    course_id: int
    folder: CourseFolder
    overwrite: bool = False
    # Only these assignments, when given; used to retry the ones refused as already downloaded.
    assignment_ids: frozenset[int] | None = None


@dataclass(frozen=True)
class AssignmentSubmissionsDownloadOutcome:
    assignment_id: int
    assignment_name: str
    saved_path: Path | None
    attachments_saved: int | None
    accepts_file_uploads: bool | None
    error: str | None
    already_downloaded: bool = False

    @property
    def status(self) -> str:
        if self.already_downloaded:
            return "already_downloaded"
        if self.error is not None:
            return "failed"
        if self.accepts_file_uploads is False:
            return "skipped"
        return "succeeded"


@dataclass(frozen=True)
class DownloadAllAssignmentSubmissionsResult:
    outcomes: tuple[AssignmentSubmissionsDownloadOutcome, ...]

    @property
    def succeeded(self) -> tuple[AssignmentSubmissionsDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "succeeded")

    @property
    def skipped(self) -> tuple[AssignmentSubmissionsDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "skipped")

    @property
    def already_downloaded(self) -> tuple[AssignmentSubmissionsDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "already_downloaded")

    @property
    def failed(self) -> tuple[AssignmentSubmissionsDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "failed")


class DownloadAllAssignmentSubmissionsUseCase:
    """Downloads Canvas submission files for every file-upload assignment in a course.
    Mirrors DownloadAllRubricAssessmentsUseCase. Eeach assignment is attempted
    independently, so one failing does not stop the rest. An assignment that
    does not accept a direct file upload (``online_upload`` not in its
    ``submission_types``) is reported as "skipped" rather than "succeeded".

    An assignment whose submissions zip is already in the course folder is
    reported as "already_downloaded" and left alone unless the request asks
    to overwrite.
    """

    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(
        self,
        request: DownloadAllAssignmentSubmissionsRequest,
        on_progress: ProgressCallback | None = None,
    ) -> DownloadAllAssignmentSubmissionsResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        log.info("Listing assignments for course %s", request.course_id)
        assignments = self._canvas_client.list_assignments(request.course_id)
        if request.assignment_ids is not None:
            assignments = [a for a in assignments if a.id in request.assignment_ids]
        total = len(assignments)
        uploadable = sum(1 for a in assignments if _accepts_file_uploads(a))
        log.info(
            "Found %d assignment(s) for course %s, %d accepting file uploads",
            total,
            request.course_id,
            uploadable,
        )
        report(on_progress, PROGRESS_LABEL, 0, total)
        submissions_use_case = DownloadAssignmentSubmissionsUseCase(self._canvas_client)

        outcomes = []
        for index, assignment in enumerate(assignments, start=1):
            log.info(
                "Assignment %d of %d: '%s' (id %s)", index, total, assignment.name, assignment.id
            )
            outcome = self._download_one(submissions_use_case, request, assignment)
            outcomes.append(outcome)
            _log_outcome(outcome, index, total)
            report(on_progress, PROGRESS_LABEL, index, total, assignment.name)

        result = DownloadAllAssignmentSubmissionsResult(outcomes=tuple(outcomes))
        log.info(
            "Assignment submissions for course %s done: %d saved, %d already downloaded, "
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
        submissions_use_case: DownloadAssignmentSubmissionsUseCase,
        request: DownloadAllAssignmentSubmissionsRequest,
        assignment: CanvasAssignment,
    ) -> AssignmentSubmissionsDownloadOutcome:
        if not _accepts_file_uploads(assignment):
            return AssignmentSubmissionsDownloadOutcome(
                assignment_id=assignment.id,
                assignment_name=assignment.name,
                saved_path=None,
                attachments_saved=None,
                accepts_file_uploads=False,
                error=None,
            )

        try:
            result = submissions_use_case.execute(
                DownloadAssignmentSubmissionsRequest(
                    course_id=request.course_id,
                    assignment=assignment,
                    folder=request.folder,
                    overwrite=request.overwrite,
                )
            )
        except ArtifactExistsError as exc:
            return AssignmentSubmissionsDownloadOutcome(
                assignment_id=assignment.id,
                assignment_name=assignment.name,
                saved_path=exc.target,
                attachments_saved=None,
                accepts_file_uploads=None,
                error=None,
                already_downloaded=True,
            )
        except Exception as exc:  # noqa: BLE001
            return AssignmentSubmissionsDownloadOutcome(
                assignment_id=assignment.id,
                assignment_name=assignment.name,
                saved_path=None,
                attachments_saved=None,
                accepts_file_uploads=None,
                error=str(exc),
            )

        return AssignmentSubmissionsDownloadOutcome(
            assignment_id=assignment.id,
            assignment_name=assignment.name,
            saved_path=result.saved_path,
            attachments_saved=result.attachments_saved,
            accepts_file_uploads=True,
            error=None,
        )


def _log_outcome(outcome: AssignmentSubmissionsDownloadOutcome, index: int, total: int) -> None:
    prefix = f"Assignment {index} of {total} '{outcome.assignment_name}'"
    if outcome.status == "succeeded":
        log.info(
            "%s: %s attachment(s) saved to %s",
            prefix,
            outcome.attachments_saved,
            outcome.saved_path,
        )
    elif outcome.status == "already_downloaded":
        log.info("%s: already downloaded at %s", prefix, outcome.saved_path)
    elif outcome.status == "skipped":
        log.info("%s: skipped, does not accept file uploads", prefix)
    else:
        log.error("%s: failed, %s", prefix, outcome.error)
