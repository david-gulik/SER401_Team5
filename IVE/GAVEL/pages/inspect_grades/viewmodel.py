
from __future__ import annotations

from pathlib import Path

from GAVEL.app.workspace.dataset import (
    CourseDataset,
    DatasetReaders,
    MissingArtifactError,
)
from GAVEL.app.workspace.layout import CourseFolder, Workspace
from GAVEL.app.workspace.manifest import AssignmentEntry, ManifestError


class InspectGradesViewModel:

    def __init__(
        self,
        workspace_root: Path,
        dataset_readers: DatasetReaders,
    ) -> None:
        self._workspace_root = workspace_root
        self._dataset_readers = dataset_readers

        self.courses: tuple[CourseFolder, ...] = ()
        self.assignments: tuple[AssignmentEntry, ...] = ()

        self.selected_course: CourseFolder | None = None
        self.selected_assignment: AssignmentEntry | None = None
        self.assignment_error: str | None = None

    def load_courses(self) -> None:
        self.courses = tuple(
            Workspace(self._workspace_root).list_courses()
        )

        self.selected_course = None
        self.selected_assignment = None
        self.assignments = ()
        self.assignment_error = None

    def select_course(self, course: CourseFolder | None) -> None:
        self.selected_course = course
        self.selected_assignment = None
        self.assignments = ()
        self.assignment_error = None

        if course is None:
            return

        dataset = CourseDataset.anonymized(course, self._dataset_readers)

        try:
            self.assignments = dataset.assignments()
        except (MissingArtifactError, ManifestError, OSError) as exc:
            self.assignment_error = str(exc)

    def select_assignment(
        self,
        assignment: AssignmentEntry | None,
    ) -> None:
        if assignment is not None and assignment not in self.assignments:
            raise ValueError("Assignment does not belong to the selected course.")

        self.selected_assignment = assignment
