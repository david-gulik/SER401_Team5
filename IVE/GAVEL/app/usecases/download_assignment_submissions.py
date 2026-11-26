"""Downloads a Canvas assignment's submitted file attachments.
This saves each student's latest submission to Canvas. Only
assignments that accept a direct file upload (``online_upload`` in
``submission_types``) are saved.
"""

from __future__ import annotations

import json
import logging
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasAttachment, CanvasSubmission
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.download_rubric_assessment import assignment_folder_for
from GAVEL.app.workspace.layout import AssignmentFolder, CourseFolder
from GAVEL.app.workspace.manifest import assignment_entry
from GAVEL.app.workspace.recording import guard_not_downloaded, note_assignment, note_course, record

log = logging.getLogger(__name__)


def build_submission_filename(
    sortable_name: str, user_id: int, attachment_id: int, filename: str
) -> str:
    """Canvas's "Download Submissions" zip entry name for one attachment.
    Documented format: ``<lastname><firstname>_<canvas user id>_<attachment
    id>_<submitted filename>``.

    Needs verification against a real Canvas export zip before this is
    trusted as exact - in particular whether Canvas adds a ``LATE_`` prefix
    for late submissions and whether a resubmission gets a ``-1``/``-2``
    suffix.
    """
    name_part = sortable_name.replace(", ", "").replace(",", "").replace(" ", "")
    return f"{name_part}_{user_id}_{attachment_id}_{filename}"


@dataclass(frozen=True)
class DownloadAssignmentSubmissionsRequest:
    course_id: int
    assignment: CanvasAssignment
    folder: CourseFolder
    overwrite: bool = False


@dataclass(frozen=True)
class FailedAttachment:
    user_id: int
    attachment_id: int
    display_name: str
    error: str


@dataclass(frozen=True)
class DownloadAssignmentSubmissionsResult:
    saved_path: Path
    assignment_folder: AssignmentFolder
    attachments_saved: int
    students_with_no_attachments: int
    failed_attachments: tuple[FailedAttachment, ...]
    message: str


class DownloadAssignmentSubmissionsUseCase:
    """Saves one assignment's Canvas-submitted files under ``assignments/``."""

    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(
        self, request: DownloadAssignmentSubmissionsRequest
    ) -> DownloadAssignmentSubmissionsResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")
        assignment = request.assignment
        if assignment.id <= 0:
            raise ValueError("assignment_id must be greater than zero")

        target_folder = assignment_folder_for(request.folder.original, assignment)
        zip_path = target_folder.submissions_zip
        guard_not_downloaded(request.folder, zip_path, request.overwrite)

        submissions = self._canvas_client.list_assignment_submissions(
            request.course_id, assignment.id
        )

        students_with_no_attachments = sum(1 for s in submissions if not s.attachments)
        failed: list[FailedAttachment] = []
        entries: list[tuple[str, CanvasSubmission, CanvasAttachment, bytes]] = []
        for submission in submissions:
            for attachment in submission.attachments:
                try:
                    content = self._canvas_client.fetch_attachment_bytes(attachment.url)
                except Exception as exc:  # noqa: BLE001 - one bad attachment must not lose the rest
                    log.warning(
                        "Could not download attachment %s for user %s: %s",
                        attachment.id,
                        submission.user_id,
                        exc,
                    )
                    failed.append(
                        FailedAttachment(
                            user_id=submission.user_id,
                            attachment_id=attachment.id,
                            display_name=attachment.display_name,
                            error=str(exc),
                        )
                    )
                    continue
                name = build_submission_filename(
                    submission.sortable_name,
                    submission.user_id,
                    attachment.id,
                    attachment.display_name,
                )
                entries.append((name, submission, attachment, content))

        target_folder.path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, _submission, _attachment, content in entries:
                archive.writestr(name, content)

        _extract(zip_path, target_folder.submissions_extracted_dir)

        sidecar = [
            {
                "user_id": submission.user_id,
                "sortable_name": submission.sortable_name,
                "late": submission.late,
                "attachment_id": attachment.id,
                "display_name": attachment.display_name,
                "saved_as": name,
            }
            for name, submission, attachment, _content in entries
        ]
        target_folder.submissions_json.write_text(
            json.dumps(sidecar, indent=2) + "\n", encoding="utf-8"
        )

        record(
            request.folder,
            "assignment_submissions",
            zip_path,
            source_id=assignment.id,
            label=assignment.name,
        )
        note_assignment(
            request.folder,
            assignment_entry(
                assignment,
                module_number=target_folder.module_number,
                has_rubric=assignment.has_rubric,
            ),
        )
        note_course(request.folder, canvas_course_id=request.course_id)

        message = (
            f"Submissions for course {request.course_id}, assignment {assignment.id} "
            f"saved to {zip_path} ({len(entries)} file(s), "
            f"{students_with_no_attachments} student(s) with nothing submitted"
        )
        if failed:
            message += f", {len(failed)} attachment(s) failed"
        message += ")"

        return DownloadAssignmentSubmissionsResult(
            saved_path=zip_path,
            assignment_folder=target_folder,
            attachments_saved=len(entries),
            students_with_no_attachments=students_with_no_attachments,
            failed_attachments=tuple(failed),
            message=message,
        )


def _extract(zip_path: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)
