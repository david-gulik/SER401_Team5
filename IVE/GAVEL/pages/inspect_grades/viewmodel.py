from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.gradescope import GradescopeSubmission
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.app.usecases.match_proxy_criteria_to_rubric import (
    match_proxy_criteria_to_rubric,
)
from GAVEL.app.usecases.proxy_grade.compute_proxy_grade import (
    MissingTestResultsError,
    compute_proxy_grade,
)
from GAVEL.app.usecases.proxy_grade.mappings.registry import MAPPINGS
from GAVEL.app.usecases.proxy_grade.submission_matching import (
    gradebook_rows_by_login,
    no_tests_ran_on_the_submitted_code,
    student_key,
)
from GAVEL.app.workspace.dataset import (
    CourseDataset,
    DatasetReaders,
    MissingArtifactError,
)
from GAVEL.app.workspace.layout import CourseFolder, Workspace
from GAVEL.app.workspace.manifest import AssignmentEntry, ManifestError
from GAVEL.pages.inspect_grades.correction_store import (
    load_corrections,
    save_corrections,
)


class InspectGradesViewModel:
    def __init__(self, dataset_readers: DatasetReaders) -> None:
        self._dataset_readers = dataset_readers

        self.assignments: tuple[AssignmentEntry, ...] = ()

        self.selected_course: CourseFolder | None = None
        self.selected_assignment: AssignmentEntry | None = None
        self.assignment_error: str | None = None

        self.human_grades: tuple[RubricAssessment, ...] = ()
        self.proxy_grades: tuple[GradescopeSubmission, ...] = ()
        self.human_grades_error: str | None = None
        self.proxy_grades_error: str | None = None
        self.rubric_definition: RubricDefinition | None = None
        self.rubric_definition_error: str | None = None
        self.corrections: dict[tuple[int, str], float] = {}
        self.notes: dict[tuple[int, str], str] = {}
        self.corrections_error: str | None = None
        self.gradebook: CanvasGradebook | None = None
        self.gradebook_error: str | None = None
        self.proxy_calculation_error: str | None = None

        self.available_autograder_zips: tuple[Path, ...] = ()
        self.selected_autograder_zip: Path | None = None
        self.autograder_zip_error: str | None = None

    def select_course(self, course: CourseFolder | None) -> None:
        self.selected_course = course
        self.selected_assignment = None
        self.assignments = ()
        self.assignment_error = None
        self._clear_grades()
        self.corrections.clear()
        self.notes.clear()
        self.corrections_error = None
        self._clear_autograder_zips()

        if course is None:
            return

        dataset = CourseDataset.anonymized(course, self._dataset_readers)

        try:
            self.assignments = dataset.assignments()
        except (MissingArtifactError, ManifestError, OSError) as exc:
            self.assignment_error = str(exc)

        self._load_autograder_zips()

    def select_assignment(
        self,
        assignment: AssignmentEntry | None,
    ) -> None:
        if assignment is not None and assignment not in self.assignments:
            raise ValueError("Assignment does not belong to the selected course.")

        self.selected_assignment = assignment
        self._clear_grades()
        self.corrections.clear()
        self.notes.clear()
        self.corrections_error = None
        self.selected_autograder_zip = None

        if assignment is None or self.selected_course is None:
            return

        path = self._corrections_path()

        if path is not None:
            try:
                self.corrections, self.notes = load_corrections(path)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.corrections_error = f"Could not load saved corrections: {exc}"

        dataset = CourseDataset.anonymized(
            self.selected_course,
            self._dataset_readers,
        )

        try:
            self.gradebook = dataset.gradebook()
        except (MissingArtifactError, OSError, ValueError, KeyError) as exc:
            self.gradebook_error = str(exc)

        if assignment.has_rubric:
            try:
                self.rubric_definition = dataset.rubric_definition(assignment.canvas_id)

                if self.rubric_definition is None:
                    self.rubric_definition_error = (
                        "Rubric definition is not available for this assignment."
                    )
            except (
                MissingArtifactError,
                ManifestError,
                OSError,
                ValueError,
                KeyError,
                IndexError,
            ) as exc:
                self.rubric_definition_error = str(exc)

            try:
                self.human_grades = dataset.rubric_assessments(assignment.canvas_id)
            except (
                MissingArtifactError,
                ManifestError,
                OSError,
                ValueError,
                KeyError,
                IndexError,
            ) as exc:
                self.human_grades_error = str(exc)
        else:
            self.human_grades_error = "This assignment has no rubric."

        if assignment.module_number is None:
            self.proxy_grades_error = "No Gradescope module is associated with this assignment."
        else:
            try:
                self.proxy_grades = tuple(dataset.gradescope_submissions(assignment.module_number))
            except (
                MissingArtifactError,
                OSError,
                BadZipFile,
                ValueError,
                KeyError,
                IndexError,
            ) as exc:
                self.proxy_grades_error = str(exc)

        if self.corrections_error is None and (self.corrections or self.notes):
            if self.rubric_definition is None or not self.human_grades:
                self.corrections.clear()
                self.notes.clear()
                self.corrections_error = (
                    "Could not validate saved corrections because "
                    "the rubric or human grades are unavailable."
                )
            else:
                try:
                    student_ids = {assessment.student_id for assessment in self.human_grades}
                    criteria = {
                        criterion.id: criterion for criterion in self.rubric_definition.criteria
                    }

                    for student_id, criterion_id in self.corrections.keys() | self.notes.keys():
                        if student_id not in student_ids:
                            raise ValueError(f"Unknown student ID: {student_id}")

                        if criterion_id not in criteria:
                            raise ValueError(f"Unknown rubric criterion: {criterion_id}")

                        score = self.corrections.get((student_id, criterion_id))
                        maximum = criteria[criterion_id].points

                        if score is not None and maximum is not None and score > maximum:
                            raise ValueError(
                                f"Corrected score {score:g} exceeds "
                                f"the maximum of {maximum:g} "
                                f"for {criterion_id}."
                            )

                except ValueError as exc:
                    self.corrections.clear()
                    self.notes.clear()
                    self.corrections_error = f"Could not load saved corrections: {exc}"

    def resolve_mapping_name(self) -> str | None:
        if self.selected_course is None or self.selected_assignment is None:
            return None

        module_number = self.selected_assignment.module_number
        if module_number is None:
            return None

        key = self.selected_course.key
        name = f"{key.subject.lower()}{key.catalog_number}_m{module_number}"

        return name if name in MAPPINGS else None

    def matched_proxy_submissions(self) -> dict[int, GradescopeSubmission]:
        if self.gradebook is None:
            return {}

        rows_by_login = gradebook_rows_by_login(self.gradebook)
        matched = {}
        duplicate_students = set()

        for submission in self.proxy_grades:
            login = student_key(submission.submitter.email)
            row = rows_by_login.get(login)

            if row is None:
                continue

            student_id = row.canvas_id

            if student_id in matched:
                duplicate_students.add(student_id)
            else:
                matched[student_id] = submission

        for student_id in duplicate_students:
            matched.pop(student_id, None)

        return matched

    def calculated_proxy_scores(self) -> dict[int, dict[str, float]]:
        self.proxy_calculation_error = None

        mapping_name = self.resolve_mapping_name()

        if mapping_name is None or self.rubric_definition is None:
            return {}

        mapping = MAPPINGS[mapping_name]

        try:
            criterion_match = match_proxy_criteria_to_rubric(
                mapping,
                self.rubric_definition,
            )
        except ValueError as exc:
            self.proxy_calculation_error = f"Could not calculate proxy grades: {exc}"
            return {}

        scores_by_student = {}

        for student_id, submission in self.matched_proxy_submissions().items():
            try:
                result = compute_proxy_grade(submission, mapping)
                criterion_scores = result.criterion_scores
            except MissingTestResultsError:
                if no_tests_ran_on_the_submitted_code(submission):
                    criterion_scores = tuple(0.0 for _ in mapping.criteria)
                else:
                    continue

            scores_by_student[student_id] = {
                criterion_match[criterion.name].id: float(score)
                for criterion, score in zip(
                    mapping.criteria,
                    criterion_scores,
                    strict=True,
                )
            }

        return scores_by_student

    def _corrections_path(self) -> Path | None:
        if self.selected_course is None or self.selected_assignment is None:
            return None

        workspace = Workspace(self.selected_course.workspace_root)
        course_dir = workspace.course_corrections_dir(self.selected_course.key)

        return course_dir / f"{self.selected_assignment.canvas_id}.json"

    def save_current_corrections(self) -> None:
        path = self._corrections_path()

        if path is None or self.corrections_error is not None:
            return

        try:
            save_corrections(
                path,
                self.corrections,
                self.notes,
            )
        except OSError as exc:
            self.corrections_error = f"Could not save rubric corrections: {exc}"

    def set_correction(
        self,
        student_id: int,
        criterion_id: str,
        corrected_score: float,
    ) -> None:
        self.corrections[(student_id, criterion_id)] = corrected_score

    def get_correction(
        self,
        student_id: int,
        criterion_id: str,
    ) -> float | None:
        return self.corrections.get((student_id, criterion_id))

    def _clear_grades(self) -> None:
        self.human_grades = ()
        self.proxy_grades = ()
        self.human_grades_error = None
        self.proxy_grades_error = None
        self.rubric_definition = None
        self.rubric_definition_error = None
        self.gradebook = None
        self.gradebook_error = None
        self.proxy_calculation_error = None

    def _clear_autograder_zips(self) -> None:
        self.available_autograder_zips = ()
        self.selected_autograder_zip = None
        self.autograder_zip_error = None

    def _load_autograder_zips(self) -> None:
        if self.selected_course is None:
            return

        workspace = Workspace(self.selected_course.workspace_root)
        directory = workspace.course_autograders_dir(self.selected_course.key)

        try:
            if directory.is_dir():
                self.available_autograder_zips = tuple(
                    sorted(
                        path
                        for path in directory.iterdir()
                        if path.is_file() and path.suffix.lower() == ".zip"
                    )
                )
        except OSError as exc:
            self.autograder_zip_error = str(exc)

    def select_autograder_zip(self, zip_path: Path | None) -> None:
        if zip_path is not None and zip_path not in self.available_autograder_zips:
            raise ValueError("Autograder ZIP is not available for this course.")

        self.selected_autograder_zip = zip_path
