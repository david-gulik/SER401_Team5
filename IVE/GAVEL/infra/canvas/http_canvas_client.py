from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import requests

from GAVEL.app.dtos.canvas_course import CanvasCourse, CanvasCourseData, CanvasModule
from GAVEL.app.ports.canvas_client import CanvasClient


@dataclass(frozen=True)
class CanvasApiConfig:
    base_url: str
    token: str


class HttpCanvasClient(CanvasClient):
    def __init__(self, config: CanvasApiConfig, session: Optional[requests.Session] = None) -> None:
        self._config = config
        self._session = session or requests.Session()

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        course_json = self._get(f"/api/v1/courses/{course_id}")
        modules_json = self._get(f"/api/v1/courses/{course_id}/modules")

        course = CanvasCourse(
            id=int(course_json["id"]),
            name=str(course_json.get("name") or course_json.get("course_code") or ""),
            course_code=course_json.get("course_code"),
        )

        modules = [
            CanvasModule(
                id=int(module["id"]),
                name=str(module.get("name") or f"Module {module['id']}"),
            )
            for module in modules_json
        ]

        return CanvasCourseData(course=course, modules=modules)

    def _get(self, path: str) -> Any:
        url = self._build_url(path)
        resp = self._session.get(
            url,
            headers={
                "Authorization": f"Bearer {self._config.token}",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        base = self._config.base_url.rstrip("/")
        suffix = path.lstrip("/")
        return f"{base}/{suffix}"
