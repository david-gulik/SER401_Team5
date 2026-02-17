from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from GAVEL.app.dtos.canvas_course import CanvasCourseData
from GAVEL.app.ports.canvas_client import CanvasClient


@dataclass(frozen=True)
class DownloadCourseDataRequest:
    course_id: int
    output_dir: Path


@dataclass(frozen=True)
class DownloadCourseDataResult:
    saved_path: Path
    message: str


class DownloadCourseDataUseCase:
    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(self, request: DownloadCourseDataRequest) -> DownloadCourseDataResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        output_dir = request.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        course_data = self._canvas_client.fetch_course_data(request.course_id)

        payload = self._serialize_course_data(course_data)
        file_path = output_dir / f"canvas_course_{course_data.course.id}.json"
        with file_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

        message = f"Canvas course '{course_data.course.name}' saved to {file_path}"
        return DownloadCourseDataResult(saved_path=file_path, message=message)

    def _serialize_course_data(self, data: CanvasCourseData) -> dict:
        return {
            "course": asdict(data.course),
            "modules": [asdict(m) for m in data.modules],
        }
