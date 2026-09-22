from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnonymizeCourseDatasetRequest:
    snapshot_dir: Path
    seed: int | None = None


@dataclass(frozen=True)
class ArtifactReport:
    processed_count: int = 0
    skipped_count: int = 0
    excluded_count: int = 0


@dataclass(frozen=True)
class AnonymizeCourseDatasetResult:
    output_dir: Path
    consent_form: ArtifactReport
    roster: ArtifactReport
    gradebook: ArtifactReport
    rubric_assessment: ArtifactReport


class AnonymizeCourseDatasetUseCase:
    def execute(
        self,
        request: AnonymizeCourseDatasetRequest,
    ) -> AnonymizeCourseDatasetResult:
        original_dir = request.snapshot_dir / "original"
        output_dir = request.snapshot_dir / "anonymized"

        consent_form_path = original_dir / "consent_form.csv"
        roster_path = original_dir / "roster.csv"
        gradebook_path = original_dir / "gradebook.csv"
        assignments_dir = original_dir / "assignments"

        raise NotImplementedError