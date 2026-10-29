from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.usecases.proxy_grade.generate_heat_map_report import (
    compute_heat_map_rows,
    write_heat_map_report,
)
from GAVEL.app.usecases.proxy_grade.generate_signed_error_report import (
    compute_signed_error_rows,
    write_report,
)
from GAVEL.app.usecases.proxy_grade.mappings.registry import MAPPINGS
from GAVEL.app.workspace.dataset import CourseDataset, DatasetReaders, MissingArtifactError
from GAVEL.app.workspace.layout import CourseFolder, Workspace
from GAVEL.app.workspace.manifest import AssignmentEntry


@dataclass(frozen=True)
class GenerateReportOutcome:
    output_path: Path
    scored: int
    unmatched: int
    failed: int


@dataclass(frozen=True)
class GenerateHeatMapOutcome:
    output_path: Path
    scored: int
    unmatched: int
    failed: int
    missing_human_scores: int


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

    def resolve_mapping_name(self, course: CourseFolder, module_number: int) -> str | None:
        """The one proxy-grade mapping for this course and module, or None if there isn't one.

        Mapping names follow ``<subject><catalog>_m<module>`` (e.g. ``ser334_m2``),
        built from the course rather than typed or picked, so the internal mapping
        name is never something a user has to know about or choose.
        """
        key = course.key
        name = f"{key.subject.lower()}{key.catalog_number}_m{module_number}"
        return name if name in MAPPINGS else None

    def list_gradebook_columns(self, course: CourseFolder, module_number: int) -> tuple[str, ...]:
        """Real gradebook column headers belonging to the given module.

        Matches a column to the module by Canvas assignment id: the manifest
        records which module each assignment belongs to, and the gradebook
        reader keys each column by that same id. A module often has more than
        one matching column (e.g. a Gradescope-synced one with no posted
        scores alongside a manually-graded one), so this narrows rather than
        picks one. Falls back to every column when none match, rather than
        hiding all of them, since that usually means the manifest has nothing
        to match against yet.
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

        matched = tuple(c.raw_header for c in gradebook.columns if c.canvas_id in matched_ids)
        return matched or tuple(c.raw_header for c in gradebook.columns)

    def list_rubric_assignments(
        self, course: CourseFolder, module_number: int
    ) -> tuple[AssignmentEntry, ...]:
        """Assignments in a module that have a rubric, for the Heat Map Report's picker."""
        dataset = CourseDataset.anonymized(course, self._dataset_readers)
        try:
            return tuple(
                entry
                for entry in dataset.assignments()
                if entry.module_number == module_number and entry.has_rubric
            )
        except MissingArtifactError:
            return ()

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

    def generate_heat_map(
        self,
        workspace_root: Path,
        course: CourseFolder,
        module_number: int,
        mapping_name: str,
        rubric_assignment: AssignmentEntry,
    ) -> GenerateHeatMapOutcome:
        dataset = CourseDataset.anonymized(course, self._dataset_readers)
        submissions = dataset.gradescope_submissions(module_number)
        gradebook = dataset.gradebook()
        mapping = MAPPINGS[mapping_name]

        rubric_definition = dataset.rubric_definition(rubric_assignment.canvas_id)
        if rubric_definition is None:
            raise MissingArtifactError(
                dataset.tree, f"rubric definition for {rubric_assignment.name}", dataset.tree.root
            )
        rubric_assessments = dataset.rubric_assessments(rubric_assignment.canvas_id)

        result = compute_heat_map_rows(
            submissions, gradebook, rubric_definition, rubric_assessments, mapping
        )

        workspace = Workspace(workspace_root)
        output_path = (
            workspace.runs_dir
            / f"{course.key.folder_name}_m{module_number}_{mapping_name}_heatmap.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_heat_map_report(result, output_path)

        return GenerateHeatMapOutcome(
            output_path=output_path,
            scored=len(result.rows),
            unmatched=len(result.unmatched_submissions),
            failed=len(result.failed_submissions),
            missing_human_scores=len(result.students_without_human_scores),
        )
