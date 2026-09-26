"""Everything Canvas has for a course, into one course folder.

The CLI's ``download-dataset`` command. Each step runs independently and
reports its own outcome, so one failing call does not leave the folder in an
unknown state: whatever did land is in the manifest.
"""

from __future__ import annotations

from dataclasses import dataclass

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.canvas_download_course import (
    DownloadCourseDataRequest,
    DownloadCourseDataUseCase,
)
from GAVEL.app.usecases.download_consent_form import (
    DownloadConsentFormRequest,
    DownloadConsentFormUseCase,
)
from GAVEL.app.usecases.download_gradebook import (
    DownloadGradebookRequest,
    DownloadGradebookUseCase,
)
from GAVEL.app.usecases.download_rubric_assessment import (
    DownloadRubricAssessmentRequest,
    DownloadRubricAssessmentUseCase,
)
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.recording import ArtifactExistsError

COURSE_STEP = "course metadata"
GRADEBOOK_STEP = "gradebook"
CONSENT_STEP = "consent form"


@dataclass(frozen=True)
class DownloadCourseDatasetRequest:
    course_id: int
    quiz_id: int
    assignment_ids: list[int]
    folder: CourseFolder
    overwrite: bool = False


@dataclass(frozen=True)
class DatasetStepOutcome:
    step: str
    status: str  # "succeeded" | "already_downloaded" | "failed"
    detail: str


@dataclass(frozen=True)
class DownloadCourseDatasetResult:
    folder: CourseFolder
    outcomes: tuple[DatasetStepOutcome, ...]
    message: str

    @property
    def succeeded(self) -> tuple[DatasetStepOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "succeeded")

    @property
    def already_downloaded(self) -> tuple[DatasetStepOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "already_downloaded")

    @property
    def failed(self) -> tuple[DatasetStepOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "failed")


class DownloadCourseDatasetUseCase:
    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(self, request: DownloadCourseDatasetRequest) -> DownloadCourseDatasetResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")
        if request.quiz_id <= 0:
            raise ValueError("quiz_id must be greater than zero")

        outcomes: list[DatasetStepOutcome] = []

        def run(step: str, action) -> None:  # noqa: ANN001
            try:
                detail = action()
            except ArtifactExistsError as exc:
                outcomes.append(DatasetStepOutcome(step, "already_downloaded", str(exc)))
            except Exception as exc:  # noqa: BLE001
                outcomes.append(DatasetStepOutcome(step, "failed", str(exc)))
            else:
                outcomes.append(DatasetStepOutcome(step, "succeeded", detail))

        run(
            COURSE_STEP,
            lambda: (
                DownloadCourseDataUseCase(self._canvas_client)
                .execute(DownloadCourseDataRequest(request.course_id, request.folder))
                .message
            ),
        )
        run(
            GRADEBOOK_STEP,
            lambda: (
                DownloadGradebookUseCase(self._canvas_client)
                .execute(
                    DownloadGradebookRequest(request.course_id, request.folder, request.overwrite)
                )
                .message
            ),
        )
        run(
            CONSENT_STEP,
            lambda: (
                DownloadConsentFormUseCase(self._canvas_client)
                .execute(
                    DownloadConsentFormRequest(
                        request.course_id, request.quiz_id, request.folder, request.overwrite
                    )
                )
                .message
            ),
        )

        if request.assignment_ids:
            known = self._known_assignments(request.course_id)
            rubric_use_case = DownloadRubricAssessmentUseCase(self._canvas_client)
            for assignment_id in request.assignment_ids:
                assignment = known.get(assignment_id, CanvasAssignment(id=assignment_id, name=""))
                run(
                    f"rubric {assignment_id}",
                    lambda a=assignment: (
                        rubric_use_case.execute(
                            DownloadRubricAssessmentRequest(
                                request.course_id, a, request.folder, request.overwrite
                            )
                        ).message
                    ),
                )

        result = DownloadCourseDatasetResult(
            folder=request.folder, outcomes=tuple(outcomes), message=""
        )
        message = (
            f"Dataset for course {request.course_id} in {request.folder.path}: "
            f"{len(result.succeeded)} saved, {len(result.already_downloaded)} already downloaded, "
            f"{len(result.failed)} failed"
        )
        return DownloadCourseDatasetResult(
            folder=request.folder, outcomes=tuple(outcomes), message=message
        )

    def _known_assignments(self, course_id: int) -> dict[int, CanvasAssignment]:
        """Names for the folder tags; empty when the list call fails."""
        try:
            return {a.id: a for a in self._canvas_client.list_assignments(course_id)}
        except Exception:  # noqa: BLE001
            return {}
