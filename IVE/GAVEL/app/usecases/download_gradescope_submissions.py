from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.gradescope_client import GradescopeClient


@dataclass(frozen=True)
class DownloadGradescopeSubmissionsRequest:
    course_id: int
    headless: bool = False


@dataclass(frozen=True)
class DownloadGradescopeSubmissionsResult:
    saved_path: Path
    message: str


class DownloadGradescopeSubmissionsUseCase:
    def execute(
        self, request: DownloadGradescopeSubmissionsRequest
    ) -> DownloadGradescopeSubmissionsResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        username = os.getenv("CANVAS_USERNAME")
        password = os.getenv("CANVAS_PASSWORD")
        if not username or not password:
            raise RuntimeError(
                "Environment variables CANVAS_USERNAME and CANVAS_PASSWORD are required."
            )

        client = GradescopeClient(
            course_url=f"https://canvas.asu.edu/courses/{request.course_id}",
            headless=request.headless,
        )
        client.download_all_assignments(username=username, password=password)

        saved_path = Path(client.submissions_folder)
        message = (
            f"Gradescope submissions for course {request.course_id} saved to {saved_path}"
        )
        return DownloadGradescopeSubmissionsResult(saved_path=saved_path, message=message)
