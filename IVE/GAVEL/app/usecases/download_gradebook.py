from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.recording import guard_not_downloaded, note_course, record


@dataclass(frozen=True)
class DownloadGradebookRequest:
    course_id: int
    folder: CourseFolder
    overwrite: bool = False


@dataclass(frozen=True)
class DownloadGradebookResult:
    saved_path: Path
    message: str


class DownloadGradebookUseCase:
    """Saves the Canvas gradebook export as ``original/gradebook.csv``."""

    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(self, request: DownloadGradebookRequest) -> DownloadGradebookResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        target = request.folder.original.gradebook_csv
        guard_not_downloaded(request.folder, target, request.overwrite)

        gradebook_bytes = self._canvas_client.fetch_gradebook_csv(request.course_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gradebook_bytes)

        record(request.folder, "gradebook", target)
        note_course(request.folder, canvas_course_id=request.course_id)

        message = f"Gradebook for course {request.course_id} saved to {target}"
        return DownloadGradebookResult(saved_path=target, message=message)
