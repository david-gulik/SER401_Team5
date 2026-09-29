from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.recording import guard_not_downloaded, note_course, record


@dataclass(frozen=True)
class DownloadConsentFormRequest:
    course_id: int
    quiz_id: int
    folder: CourseFolder
    overwrite: bool = False


@dataclass(frozen=True)
class DownloadConsentFormResult:
    saved_path: Path
    message: str


class DownloadConsentFormUseCase:
    """Saves the consent quiz's student analysis export as ``original/consent_form.csv``."""

    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(self, request: DownloadConsentFormRequest) -> DownloadConsentFormResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")
        if request.quiz_id <= 0:
            raise ValueError("quiz_id must be greater than zero")

        target = request.folder.original.consent_form_csv
        guard_not_downloaded(request.folder, target, request.overwrite)

        consent_bytes = self._canvas_client.fetch_quiz_student_analysis(
            request.course_id, request.quiz_id
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(consent_bytes)

        record(request.folder, "consent_form", target, source_id=request.quiz_id)
        note_course(request.folder, canvas_course_id=request.course_id)

        message = f"Consent form for course {request.course_id} saved to {target}"
        return DownloadConsentFormResult(saved_path=target, message=message)
