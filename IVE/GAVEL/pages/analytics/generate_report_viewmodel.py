from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.usecases.proxy_grade.generate_signed_error_report import (
    compute_signed_error_rows,
    write_report,
)
from GAVEL.app.usecases.proxy_grade.mappings.registry import MAPPINGS
from GAVEL.app.workspace.dataset import CourseDataset, DatasetReaders, MissingArtifactError
from GAVEL.app.workspace.layout import CourseFolder, Workspace


@dataclass(frozen=True)
class GenerateReportOutcome:
    output_path: Path
    scored: int
    unmatched: int
    failed: int


class GenerateReportViewModel:
    """Runs the proxy-grade report against a course already in the workspace.

    Always reads from the anonymized side of the course folder, never the
    original, so the report it produces never carries identifying data.
    """

    def __init__(self, dataset_readers: DatasetReaders) -> None:
        self._dataset_readers = dataset_readers

    def list_courses(self, workspace_root: Path) -> tuple[CourseFolder, ...]:
        return tuple(Workspace(workspace_root).list_courses())

    def list_modules(self, course: CourseFolder) -> tuple[int, ...]:
        return tuple(
            module.module_number
            for module in course.anonymized.list_module_submissions()
            if module.exists()
        )

    def mapping_names(self) -> tuple[str, ...]:
        return tuple(sorted(MAPPINGS))

    def list_gradebook_columns(self, course: CourseFolder, module_number: int) -> tuple[str, ...]:
        """Real gradebook column headers, with the selected module's own listed first.

        Matches a column to the module by Canvas assignment id: the manifest
        records which module each assignment belongs to, and the gradebook
        reader keys each column by that same id.
        """
        dataset = CourseDataset.anonymized(course, self._dataset_readers)
        gradebook = dataset.gradebook()

        try:
            matched_ids = {
                entry.canvas_id
                for entry in dataset.assignments()
                if entry.module_number == module_number
            }
        except MissingArtifactError:
            matched_ids = set()

        matched = [c.raw_header for c in gradebook.columns if c.canvas_id in matched_ids]
        rest = [c.raw_header for c in gradebook.columns if c.canvas_id not in matched_ids]
        return tuple(matched + rest)

    def generate(
        self,
        workspace_root: Path,
        course: CourseFolder,
        module_number: int,
        mapping_name: str,
        gradebook_column: str,
    ) -> GenerateReportOutcome:
        dataset = CourseDataset.anonymized(course, self._dataset_readers)
        submissions = dataset.gradescope_submissions(module_number)
        gradebook = dataset.gradebook()
        mapping = MAPPINGS[mapping_name]

        result = compute_signed_error_rows(submissions, gradebook, gradebook_column, mapping)

        workspace = Workspace(workspace_root)
        output_path = (
            workspace.runs_dir / f"{course.key.folder_name}_m{module_number}_{mapping_name}.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_report(result, output_path)

        return GenerateReportOutcome(
            output_path=output_path,
            scored=len(result.rows),
            unmatched=len(result.unmatched_submissions),
            failed=len(result.failed_submissions),
        )
