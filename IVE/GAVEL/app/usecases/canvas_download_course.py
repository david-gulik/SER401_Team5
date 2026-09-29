from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.recording import note_course


@dataclass(frozen=True)
class DownloadCourseDataRequest:
    course_id: int
    folder: CourseFolder


@dataclass(frozen=True)
class DownloadCourseDataResult:
    saved_path: Path
    message: str


class DownloadCourseDataUseCase:
    """Records the Canvas course's name, code and modules in ``manifest.json``.

    There is no separate course file any more: the manifest is where course
    metadata lives, so this can be re-run to refresh it at any time.
    """

    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(self, request: DownloadCourseDataRequest) -> DownloadCourseDataResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        course_data = self._canvas_client.fetch_course_data(request.course_id)
        note_course(
            request.folder,
            canvas_course_id=course_data.course.id,
            canvas_course_name=course_data.course.name,
            canvas_course_code=course_data.course.course_code,
            modules=tuple(course_data.modules),
        )

        path = request.folder.manifest_path
        message = (
            f"Canvas course '{course_data.course.name}' "
            f"({len(course_data.modules)} modules) recorded in {path}"
        )
        return DownloadCourseDataResult(saved_path=path, message=message)
