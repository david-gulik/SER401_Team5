from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import requests
import time

from GAVEL.app.dtos.canvas_course import (
    CanvasCourse, CanvasCourseData, CanvasModule)
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook


@dataclass(frozen=True)
class CanvasApiConfig:
    base_url: str
    token: str


class HttpCanvasClient(CanvasClient):
    def __init__(self, config: CanvasApiConfig,
                 session: Optional[requests.Session] = None) -> None:
        self._config = config
        self._session = session or requests.Session()

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        course_json = self._get(f"/api/v1/courses/{course_id}")
        modules_json = self._get(f"/api/v1/courses/{course_id}/modules")

        course = CanvasCourse(
            id=int(course_json["id"]),
            name=str(course_json.get("name")
                     or course_json.get("course_code") or ""),
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

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        raise NotImplementedError("Gradebook CSV export not implemented yet")

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
   
    def _post(self, path: str, json: Any = None) -> Any:
        """POST to a Canvas API endpoint and return JSON."""
        url = self._build_url(path)
        resp = self._session.post(
            url,
            json=json,
            headers={
                "Authorization": f"Bearer {self._config.token}",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()
    
    def _poll_progress(
            self, progress_url: str,
            interval: int = 2, 
            max_attempts: int = 30) -> None:
        """Poll a Canvas progress URL until completion."""
        for attempt in range(max_attempts):
            data = self._get(progress_url)
            state = data.get("workflow_state")
            if state == "completed":
                return
            if state == "failed":
                raise RuntimeError("Canvas report generation failed.")
            time.sleep(interval)
        raise RuntimeError("Canvas report generation timed out.")
    
    def _download(self, url: str) -> bytes:
        """Download raw bytes from a URL with auth."""
        resp = self._session.get(
            url,
            headers={
                "Authorization": f"Bearer {self._config.token}",
            },
        )
        resp. raise_for_status()
        return resp.content
    
    def fetch_quiz_student_analysis(
            self, course_id: int, quiz_id: int) -> bytes:
        """Retrieve the student analysis CSV for a Canvas quiz."""
        report = self._post(
            f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/reports",
            json={
                "quiz_report": {
                    "report_type": "student_analysis",
                    "includes_all_versions": True,
                }
            },
        )
        progress_url = report.get("progress_url")
        if progress_url:
            self._poll_progress(progress_url)
        report_url = (
            f"/api/v1/courses/{course_id}/quizzes/{quiz_id}"
            f"/reports/{report['id']}"
        )
        report_data = self._get(report_url)
        csv_url = report_data["file"]["url"]
        return self._download(csv_url)

    def fetch_gradebook(self, course_id: int) -> CanvasGradebook:
        raise NotImplementedError