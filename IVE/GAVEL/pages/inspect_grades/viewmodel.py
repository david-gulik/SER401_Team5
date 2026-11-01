from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile

from GAVEL.app.dtos.gradescope import GradescopeSubmission
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
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

        self.human_grades: tuple[RubricAssessment, ...] = ()
        self.proxy_grades: tuple[GradescopeSubmission, ...] = ()
        self.human_grades_error: str | None = None
        self.proxy_grades_error: str | None = None

    def load_courses(self) -> None:
        self.courses = tuple(Workspace(self._workspace_root).list_courses())

        self.selected_course = None
        self.selected_assignment = None
        self.assignments = ()
        self.assignment_error = None
        self._clear_grades()

    def select_course(self, course: CourseFolder | None) -> None:
        self.selected_course = course
        self.selected_assignment = None
        self.assignments = ()
        self.assignment_error = None
        self._clear_grades()

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
        self._clear_grades()

        if assignment is None or self.selected_course is None:
            return

        dataset = CourseDataset.anonymized(self.selected_course, self._dataset_readers)

        if assignment.has_rubric:
            try:
                self.human_grades = dataset.rubric_assessments(assignment.canvas_id)
            except (MissingArtifactError, ManifestError, OSError, ValueError) as exc:
                self.human_grades_error = str(exc)
        else:
            self.human_grades_error = "This assignment has no rubric."

        if assignment.module_number is None:
            self.proxy_grades_error = "No Gradescope module is associated with this assignment."
        else:
            try:
                self.proxy_grades = tuple(dataset.gradescope_submissions(assignment.module_number))
            except (MissingArtifactError, OSError, BadZipFile, ValueError) as exc:
                self.proxy_grades_error = str(exc)

    def _clear_grades(self) -> None:
        self.human_grades = ()
        self.proxy_grades = ()
        self.human_grades_error = None
        self.proxy_grades_error = None
