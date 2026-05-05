from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.canvas_client import CanvasClient


@dataclass(frozen=True)
class DownloadConsentFormRequest:
    course_id: int
    quiz_id: int
    output_dir: Path


@dataclass(frozen=True)
class DownloadConsentFormResult:
    saved_path: Path
    message: str


class DownloadConsentFormUseCase:
    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(self, request: DownloadConsentFormRequest) -> DownloadConsentFormResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")
        if request.quiz_id <= 0:
            raise ValueError("quiz_id must be greater than zero")

        request.output_dir.mkdir(parents=True, exist_ok=True)

        consent_bytes = self._canvas_client.fetch_quiz_student_analysis(
            request.course_id, request.quiz_id
        )
        path = request.output_dir / f"consent_form_{request.course_id}.csv"
        path.write_bytes(consent_bytes)

        message = f"Consent form for course {request.course_id} saved to {path}"
        return DownloadConsentFormResult(saved_path=path, message=message)
