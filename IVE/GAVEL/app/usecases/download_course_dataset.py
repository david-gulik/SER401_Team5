from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from datetime import datetime, timezone

from GAVEL.app.ports.canvas_client import CanvasClient


@dataclass(frozen=True)
class DownloadCourseDatasetRequest:
    course_id: int
    quiz_id: int
    assignment_ids: list[int]
    output_dir: Path


@dataclass(frozen=True)
class DownloadCourseDatasetResult:
    dataset_path: Path
    message: str


class DownloadCourseDatasetUseCase:
    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(self, request: DownloadCourseDatasetRequest) -> DownloadCourseDatasetResult:

        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        dataset_dir = request.output_dir / f"dataset_{request.course_id}"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        gradebook_bytes = self._canvas_client.fetch_gradebook_csv(request.course_id)
        gradebook_path = dataset_dir / "gradebook.csv"
        gradebook_path.write_bytes(gradebook_bytes)

        consent_bytes = self._canvas_client.fetch_quiz_student_analysis(
            request.course_id, request.quiz_id
        )
        consent_path = dataset_dir / "consent_form.csv"
        consent_path.write_bytes(consent_bytes)

        rubric_dir = dataset_dir / "rubric_assessments"
        rubric_dir.mkdir(exist_ok=True)

        rubric_files = []

        for assignment_id in request.assignment_ids or []:
            assessments = self._canvas_client.fetch_rubric_assessments(
                request.course_id, assignment_id
            )

            payload = [asdict(a) for a in assessments]

            file_path = rubric_dir / f"assignment_{assignment_id}.json"
            with file_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)

            rubric_files.append(file_path)

        manifest = {
            "course_id": request.course_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "gradebook_csv": gradebook_path.name,
            "consent_form_csv": consent_path.name,
            "rubric_assessments": [f"rubric_assessments/{p.name}" for p in rubric_files],
        }

        manifest_path = dataset_dir / "dataset_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)

        message = f"Dataset for course {request.course_id} saved to {dataset_dir}"
        return DownloadCourseDatasetResult(
            dataset_path=dataset_dir,
            message=message,
        )
