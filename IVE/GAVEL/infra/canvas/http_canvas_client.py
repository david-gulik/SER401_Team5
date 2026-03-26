from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

from GAVEL.app.dtos.canvas_course import CanvasCourse, CanvasCourseData, CanvasModule
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.ports.canvas_client import CanvasClient


@dataclass(frozen=True)
class CanvasApiConfig:
    base_url: str
    token: str
    account_id: int
    poll_interval_seconds: float = 2.0
    export_timeout_seconds: float = 60.0
    max_retries: int = 3


class HttpCanvasClient(CanvasClient):
    def __init__(self, config: CanvasApiConfig, session: requests.Session | None = None) -> None:
        self._config = config
        self._session = session or requests.Session()

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        course_json = self._get_json(f"/api/v1/courses/{course_id}")
        modules_json = self._get_json(f"/api/v1/courses/{course_id}/modules")

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

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        report = self._start_gradebook_export(course_id)
        report_id_raw = report.get("id")
        if report_id_raw is None:
            raise RuntimeError(f"Canvas export request did not return a report ID: {report}")
        report_id = int(report_id_raw)

        deadline = time.monotonic() + self._config.export_timeout_seconds

        while time.monotonic() < deadline:
            status = self._get_gradebook_export_status(report_id)
            workflow_state = str(status.get("workflow_state", "")).lower()

            if workflow_state in {"complete", "completed"}:
                download_url = self._extract_gradebook_export_url(status)
                return self._get_bytes(download_url)

            if workflow_state in {"error", "failed"}:
                raise RuntimeError(f"Canvas gradebook export failed: {status}")

            time.sleep(self._config.poll_interval_seconds)

        raise TimeoutError("Timed out waiting for Canvas gradebook export to complete")

    def _start_gradebook_export(self, course_id: int) -> dict[str, Any]:
        data = {
            "parameters[course_id]": str(course_id),
        }
        return self._post_json(
            f"/api/v1/accounts/{self._config.account_id}/reports/grade_export_csv",
            data=data,
        )

    def _get_gradebook_export_status(self, report_id: int) -> dict[str, Any]:
        return self._get_json(
            f"/api/v1/accounts/{self._config.account_id}/reports/grade_export_csv/{report_id}"
        )

    def _extract_gradebook_export_url(self, status: dict[str, Any]) -> str:
        file_url = status.get("file_url")
        if isinstance(file_url, str) and file_url.strip():
            return file_url

        attachment = status.get("attachment")
        if isinstance(attachment, dict):
            attachment_url = attachment.get("url")
            if isinstance(attachment_url, str) and attachment_url.strip():
                return attachment_url

        raise RuntimeError(f"Canvas export completed but no download URL was returned: {status}")

    def _get(self, path: str) -> Any:
        """GET JSON from Canvas API."""
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

    def _get_json(self, path: str) -> Any:
        resp = self._request_with_retries(
            method="GET",
            path=path,
            accept="application/json",
        )
        return resp.json()

    def _get_bytes(self, path: str) -> bytes:
        resp = self._request_with_retries(
            method="GET",
            path=path,
            accept="*/*",
        )
        return resp.content

    def _post_json(self, path: str, data: dict[str, Any] | None = None) -> Any:
        resp = self._request_with_retries(
            method="POST",
            path=path,
            accept="application/json",
            data=data or {},
        )
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

    def _poll_progress(self, progress_url: str, interval: int = 2, max_attempts: int = 30) -> None:
        """Poll a Canvas progress URL until completion."""
        for _attempt in range(max_attempts):
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
        resp.raise_for_status()
        return resp.content

    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
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
        report_url = f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/reports/{report['id']}"
        report_data = self._get(report_url)
        csv_url = report_data["file"]["url"]
        return self._download(csv_url)

    def _request_with_retries(
        self,
        method: str,
        path: str,
        accept: str,
        data: dict[str, Any] | None = None,
    ) -> requests.Response:
        url = self._build_url(path)

        for attempt in range(self._config.max_retries + 1):
            resp = self._session.request(
                method=method,
                url=url,
                headers={
                    "Authorization": f"Bearer {self._config.token}",
                    "Accept": accept,
                },
                data=data,
            )

            if resp.status_code == 429 and attempt < self._config.max_retries:
                retry_after = resp.headers.get("Retry-After")
                sleep_seconds = (
                    float(retry_after) if retry_after else self._config.poll_interval_seconds
                )
                time.sleep(sleep_seconds)
                continue

            resp.raise_for_status()
            return resp

        raise RuntimeError(f"Request failed after retries: {method} {url}")

    def fetch_gradebook(self, course_id: int) -> CanvasGradebook:
        raise NotImplementedError
