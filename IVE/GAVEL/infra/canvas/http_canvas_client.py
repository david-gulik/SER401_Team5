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
        import csv
        from io import StringIO

        enrollments = self._get_all_pages(
            f"/api/v1/courses/{course_id}/enrollments",
            params={
                "type[]": ["StudentEnrollment"],
                "state[]": ["active", "completed", "invited"],
                "include[]": ["email", "avatar_url"],
            },
        )

        assignment_groups = self._get_all_pages(
            f"/api/v1/courses/{course_id}/assignment_groups",
            params={
                "include[]": ["assignments", "submission"],
            },
        )

        grouped_submissions = self._get_all_pages(
            f"/api/v1/courses/{course_id}/students/submissions",
            params={
                "student_ids[]": ["all"],
                "grouped": "true",
                "include[]": ["total_scores"],
                "enrollment_state": "active",
            },
        )

        assignment_columns, assignment_group_columns = self._build_gradebook_columns(
            assignment_groups
        )

        grouped_lookup = self._build_grouped_submission_lookup(
            grouped_submissions,
            assignment_columns,
        )

        output = StringIO()
        writer = csv.writer(output)

        header = ["Student Name", "Student ID"]
        header.extend([col["name"] for col in assignment_columns])
        header.extend([col["name"] for col in assignment_group_columns])
        header.append("Final Grade")
        writer.writerow(header)

        for enrollment in enrollments:
            user = enrollment.get("user", {}) or {}
            student_id = user.get("id") or enrollment.get("user_id") or ""
            student_name = user.get("name") or user.get("sortable_name") or ""

            student_submission_bundle = grouped_lookup.get(student_id, {})
            assignment_scores = student_submission_bundle.get("assignment_scores", {})
            group_totals = student_submission_bundle.get("group_totals", {})

            row = [student_name, student_id]

            for col in assignment_columns:
                row.append(assignment_scores.get(col["assignment_id"], ""))

            for col in assignment_group_columns:
                row.append(group_totals.get(col["group_name"], ""))

            final_score = student_submission_bundle.get("computed_final_score", "")
            row.append(round(final_score, 2) if isinstance(final_score, float) else final_score)
            writer.writerow(row)

        return output.getvalue().encode("utf-8")

    def _build_gradebook_columns(
        self,
        assignment_groups: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        assignment_columns: list[dict[str, Any]] = []
        assignment_group_columns: list[dict[str, Any]] = []

        sorted_groups = sorted(
            assignment_groups,
            key=lambda g: (
                g.get("position", 0),
                str(g.get("name", "")).lower(),
            ),
        )

        for group in sorted_groups:
            group_name = str(group.get("name") or "").strip()
            if not group_name:
                continue

            assignment_group_columns.append(
                {
                    "name": f"{group_name} Total",
                    "group_name": group_name,
                }
            )

            assignments = group.get("assignments", []) or []
            assignments = sorted(
                assignments,
                key=lambda a: (
                    a.get("position", 0),
                    str(a.get("name", "")).lower(),
                ),
            )

            for assignment in assignments:
                if assignment.get("omit_from_final_grade"):
                    continue

                assignment_id = assignment.get("id")
                if assignment_id is None:
                    continue

                assignment_columns.append(
                    {
                        "assignment_id": assignment_id,
                        "name": str(assignment.get("name") or ""),
                        "group_name": group_name,
                    }
                )

        return assignment_columns, assignment_group_columns

    def _build_grouped_submission_lookup(
        self,
        grouped_submissions: list[dict[str, Any]],
        assignment_columns: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:

        lookup: dict[int, dict[str, Any]] = {}

        assignment_to_group = {
            col["assignment_id"]: col["group_name"] for col in assignment_columns
        }

        for student_bundle in grouped_submissions:
            user_id = student_bundle.get("user_id")
            if user_id is None:
                continue

            submissions = student_bundle.get("submissions", []) or []

            assignment_scores: dict[int, Any] = {}
            group_totals: dict[str, float] = {}

            for submission in submissions:
                assignment_id = submission.get("assignment_id")
                if assignment_id is None:
                    continue

                score = submission.get("score")
                assignment_scores[assignment_id] = score if score is not None else ""
                group_name = assignment_to_group.get(assignment_id)
                if group_name and score is not None:
                    group_totals[group_name] = group_totals.get(group_name, 0.0) + float(score)

            lookup[user_id] = {
                "assignment_scores": assignment_scores,
                "group_totals": group_totals,
                "computed_final_score": student_bundle.get("computed_final_score", ""),
            }

        return lookup

    def _get_all_pages(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        next_url: str | None = self._build_url(path)
        query_params = params or {}

        while next_url:
            resp = self._session.request(
                method="GET",
                url=next_url,
                headers={
                    "Authorization": f"Bearer {self._config.token}",
                    "Accept": "application/json",
                },
                params=query_params if next_url == self._build_url(path) else None,
            )

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                sleep_seconds = (
                    float(retry_after) if retry_after else self._config.poll_interval_seconds
                )
                time.sleep(sleep_seconds)
                continue

            resp.raise_for_status()

            page_json = resp.json()
            if isinstance(page_json, list):
                results.extend(page_json)
            else:
                results.append(page_json)

            next_url = self._extract_next_link(resp.headers.get("Link"))
            query_params = {}

        return results

    def _extract_next_link(self, link_header: str | None) -> str | None:
        if not link_header:
            return None

        parts = [part.strip() for part in link_header.split(",")]
        for part in parts:
            if 'rel="next"' not in part:
                continue
            start = part.find("<")
            end = part.find(">")
            if start != -1 and end != -1 and end > start:
                return part[start + 1 : end]

        return None

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
