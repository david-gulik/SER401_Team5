from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.canvas_client import CanvasClient


@dataclass(frozen=True)
class DownloadGradebookRequest:
    course_id: int
    output_dir: Path


@dataclass(frozen=True)
class DownloadGradebookResult:
    saved_path: Path
    message: str


class DownloadGradebookUseCase:
    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(self, request: DownloadGradebookRequest) -> DownloadGradebookResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        request.output_dir.mkdir(parents=True, exist_ok=True)

        gradebook_bytes = self._canvas_client.fetch_gradebook_csv(request.course_id)
        path = request.output_dir / f"gradebook_{request.course_id}.csv"
        path.write_bytes(gradebook_bytes)

        message = f"Gradebook for course {request.course_id} saved to {path}"
        return DownloadGradebookResult(saved_path=path, message=message)
