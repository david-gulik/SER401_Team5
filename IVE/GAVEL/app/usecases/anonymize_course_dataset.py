from __future__ import annotations

import csv
import json
import logging
import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from GAVEL.app.dtos.asu_roster import RosterStudent
from GAVEL.app.dtos.consent_decision import ConsentDecision
from GAVEL.app.usecases.anonymize_consent_form import (
    AnonymizeConsentFormRequest,
    AnonymizeConsentFormUseCase,
)
from GAVEL.app.usecases.anonymize_gradebook import (
    AnonymizeGradebookRequest,
    AnonymizeGradebookUseCase,
)
from GAVEL.app.usecases.anonymize_gradescope_submissions import (
    AnonymizeGradescopeSubmissionsRequest,
    AnonymizeGradescopeSubmissionsUseCase,
)
from GAVEL.app.usecases.anonymize_gradescope_yml import (
    AnonymizeGradescopeYMLRequest,
    AnonymizeGradescopeYMLUseCase,
)
from GAVEL.app.usecases.anonymize_roster import (
    AnonymizeRosterRequest,
    AnonymizeRosterUseCase,
)
from GAVEL.app.usecases.anonymize_rubric_assessment import (
    AnonymizeRubricAssessmentRequest,
    AnonymizeRubricAssessmentResult,
    AnonymizeRubricAssessmentUseCase,
)
from GAVEL.app.usecases.downselect_consented_students import (
    DownselectConsentedStudentsRequest,
    DownselectConsentedStudentsUseCase,
)
from GAVEL.app.usecases.generate_anonymous_id_map import (
    GenerateAnonymousIdMapRequest,
    GenerateAnonymousIdMapUseCase,
)
from GAVEL.app.workspace.layout import RUBRIC_DEFINITION_FILE, CourseFolder, CourseKey
from GAVEL.app.workspace.recording import hash_sources, note_anonymization
from GAVEL.infra.csv.canvas_consent_form_csv_reader import (
    CanvasConsentFormCSVReader,
)
from GAVEL.infra.csv.canvas_gradebook_csv_reader import LegacyGradebookCSVReader
from GAVEL.infra.csv.canvas_roster_csv_reader import CanvasRosterCSVReader
from GAVEL.infra.json.rubric_assessment_json_reader import (
    RubricAssessmentJSONReader,
)
from GAVEL.infra.yaml.yaml_gradescope_reader import YamlGradescopeReader

log = logging.getLogger(__name__)

_T = TypeVar("_T")

_Ids = tuple[int, ...]
_IdMap = tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class AnonymizeCourseDatasetRequest:
    snapshot_dir: Path
    seed: int | None = None
    replace_existing: bool = False


@dataclass(frozen=True)
class ArtifactReport:
    processed_count: int = 0
    skipped_count: int = 0
    excluded_count: int = 0


@dataclass(frozen=True)
class ArtifactFailure:
    """An input the run could not anonymize.

    Whatever the run had written for it is removed and its hash is not
    recorded, so the course reads as out of date until a later run succeeds.
    """

    # Relative to original/, with "/" separators.
    path: str
    # The exception's type name only; messages can quote the student data
    # that failed to parse.
    error: str


@dataclass(frozen=True)
class AnonymizeCourseDatasetResult:
    output_dir: Path
    consent_form: ArtifactReport
    roster: ArtifactReport
    gradebook: ArtifactReport
    rubric_assessment: ArtifactReport
    # Why each student was kept or left out, including roster students who
    # never submitted the consent form.
    consent_decisions: tuple[ConsentDecision, ...]
    failures: tuple[ArtifactFailure, ...] = ()

    def failure(self, path: str) -> ArtifactFailure | None:
        return next((f for f in self.failures if f.path == path), None)


class _FailureLog:
    """Runs each input's step on its own, so one bad file does not stop the rest."""

    def __init__(self, original_dir: Path) -> None:
        self._original_dir = original_dir
        self.failures: list[ArtifactFailure] = []
        self.failed_inputs: set[Path] = set()

    def attempt(
        self,
        action: Callable[..., _T],
        *args: object,
        inputs: tuple[Path, ...],
        outputs: Iterable[Path] = (),
    ) -> _T | None:
        """``action(*args)``, or None after recording a failure against ``inputs[0]``.

        Every input listed is left out of the recorded sources, and every
        output is deleted so no partial file is mistaken for a finished one.
        """
        try:
            return action(*args)
        except Exception as exc:
            relative = inputs[0].relative_to(self._original_dir).as_posix()
            log.warning("Could not anonymize %s", relative, exc_info=True)
            for output in outputs:
                if output.is_dir():
                    shutil.rmtree(output, ignore_errors=True)
                else:
                    output.unlink(missing_ok=True)
            self.failures.append(ArtifactFailure(path=relative, error=type(exc).__name__))
            self.failed_inputs.update(inputs)
            return None

    def failed(self, path: Path) -> bool:
        return path in self.failed_inputs


class AnonymizeCourseDatasetUseCase:
    def __init__(
        self,
        consent_form_reader: CanvasConsentFormCSVReader,
        downselect_use_case: DownselectConsentedStudentsUseCase,
        id_map_use_case: GenerateAnonymousIdMapUseCase,
        roster_reader: CanvasRosterCSVReader,
        anonymize_roster_use_case: AnonymizeRosterUseCase,
        gradebook_reader: LegacyGradebookCSVReader,
        anonymize_gradebook_use_case: AnonymizeGradebookUseCase,
        anonymize_consent_form_use_case: AnonymizeConsentFormUseCase,
        rubric_reader: RubricAssessmentJSONReader,
        anonymize_rubric_use_case: AnonymizeRubricAssessmentUseCase,
        gradescope_reader: YamlGradescopeReader,
        anonymize_gradescope_use_case: AnonymizeGradescopeSubmissionsUseCase,
        anonymize_gradescope_yml_use_case: AnonymizeGradescopeYMLUseCase,
    ) -> None:
        self._consent_form_reader = consent_form_reader
        self._downselect_use_case = downselect_use_case
        self._id_map_use_case = id_map_use_case
        self._roster_reader = roster_reader
        self._anonymize_roster_use_case = anonymize_roster_use_case
        self._gradebook_reader = gradebook_reader
        self._anonymize_gradebook_use_case = anonymize_gradebook_use_case
        self._anonymize_consent_form_use_case = anonymize_consent_form_use_case
        self._rubric_reader = rubric_reader
        self._anonymize_rubric_use_case = anonymize_rubric_use_case
        self._gradescope_reader = gradescope_reader
        self._anonymize_gradescope_use_case = anonymize_gradescope_use_case
        self._anonymize_gradescope_yml_use_case = anonymize_gradescope_yml_use_case

    def execute(
        self,
        request: AnonymizeCourseDatasetRequest,
    ) -> AnonymizeCourseDatasetResult:
        """Anonymize everything in ``original/`` that can be, into ``anonymized/``.

        The consent form decides who is kept and drives the anonymous IDs, so
        a problem with it stops the run. Every other file is attempted on its
        own; one that fails is reported in ``failures`` and the rest still run.
        """
        original_dir = request.snapshot_dir / "original"
        output_dir = request.snapshot_dir / "anonymized"
        consent_form_path = original_dir / "consent_form.csv"
        roster_path = original_dir / "roster.csv"
        gradebook_path = original_dir / "gradebook.csv"
        assignments_dir = original_dir / "assignments"
        submissions_dir = original_dir / "submissions"

        if not consent_form_path.exists():
            raise ValueError("Consent form is missing from the dataset")

        # One rubric_assessments.json per assignment folder; see docs/workspace_layout.md.
        rubric_files = sorted(assignments_dir.rglob("rubric_assessments.json"))
        rubric_definition_files = [p.parent / RUBRIC_DEFINITION_FILE for p in rubric_files]

        course_folder = _course_folder(request.snapshot_dir)
        inputs = [
            path
            for path in (
                consent_form_path,
                roster_path,
                gradebook_path,
                *rubric_files,
                *rubric_definition_files,
            )
            if path.exists()
        ]
        # Hashed before reading, so an input that changes mid-run reads as out of date.
        sources = hash_sources(course_folder, inputs) if course_folder is not None else ()

        if request.replace_existing and output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        failures = _FailureLog(original_dir)

        consent_entries = tuple(self._consent_form_reader.read(str(consent_form_path)))

        roster_students = None
        if roster_path.exists():
            roster_students = failures.attempt(
                lambda: tuple(self._roster_reader.read(roster_path)),
                inputs=(roster_path,),
            )

        consent_result = self._downselect_use_case.execute(
            DownselectConsentedStudentsRequest(
                entries=consent_entries,
                roster=roster_students or (),
            )
        )

        id_map_result = self._id_map_use_case.execute(
            GenerateAnonymousIdMapRequest(
                student_ids=set(consent_result.consented_ids),
                seed=request.seed,
            )
        )

        id_map = tuple(id_map_result.id_map.items())

        canvas_to_anon = dict(id_map)

        sis_to_canvas = {entry.sis_id: entry.canvas_id for entry in consent_entries}

        consented_canvas_ids = set(consent_result.consented_ids)

        roster_id_map = tuple(
            (sis_id, canvas_to_anon[canvas_id])
            for sis_id, canvas_id in sis_to_canvas.items()
            if canvas_id in canvas_to_anon
        )

        roster_consented_ids = tuple(
            sis_id
            for sis_id, canvas_id in sis_to_canvas.items()
            if canvas_id in consented_canvas_ids
        )

        consent_form_result = self._anonymize_consent_form_use_case.execute(
            AnonymizeConsentFormRequest(
                entries=consent_entries,
                id_map=id_map,
            )
        )

        consent_form_output_path = output_dir / "consent_form.csv"

        with consent_form_output_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:
            writer = csv.writer(f)

            writer.writerow(
                [
                    "sis_id",
                    "name",
                    "attempt",
                    "leave blank if anonymized",
                    "Do you consent",
                ]
            )

            for entry in consent_form_result.entries:
                writer.writerow(
                    [
                        entry.sis_id,
                        entry.lms_name,
                        entry.attempt,
                        entry.name_response,
                        entry.consented,
                    ]
                )

        if roster_students is not None:
            roster_output_path = output_dir / "roster.csv"
            roster_report = failures.attempt(
                self._write_roster,
                roster_students,
                roster_consented_ids,
                roster_id_map,
                roster_output_path,
                inputs=(roster_path,),
                outputs=(roster_output_path,),
            )
        elif not roster_path.exists():
            roster_report = ArtifactReport(skipped_count=1)
        else:
            roster_report = None

        if gradebook_path.exists():
            gradebook_output_path = output_dir / "gradebook.csv"
            gradebook_report = failures.attempt(
                self._write_gradebook,
                gradebook_path,
                consent_result.consented_ids,
                id_map,
                gradebook_output_path,
                inputs=(gradebook_path,),
                outputs=(gradebook_output_path,),
            )
        else:
            gradebook_report = ArtifactReport(skipped_count=1)

        rubric_results: list[AnonymizeRubricAssessmentResult] = []

        for rubric_path in rubric_files:
            relative_path = rubric_path.relative_to(assignments_dir)
            rubric_output_path = output_dir / "assignments" / relative_path
            definition_path = rubric_path.parent / RUBRIC_DEFINITION_FILE

            rubric_result = failures.attempt(
                self._write_rubric,
                rubric_path,
                consent_result.consented_ids,
                id_map,
                request.seed,
                rubric_output_path,
                inputs=(rubric_path, definition_path),
                outputs=(
                    rubric_output_path,
                    rubric_output_path.parent / RUBRIC_DEFINITION_FILE,
                ),
            )
            if rubric_result is not None:
                rubric_results.append(rubric_result)

        rubric_skipped = sum(result.skipped_count for result in rubric_results)

        rubric_excluded = sum(result.excluded_count for result in rubric_results)

        rubric_processed = sum(len(result.assessments) for result in rubric_results)

        if submissions_dir.exists():
            self._anonymize_submissions(
                submissions_dir,
                output_dir / "submissions",
                set(roster_consented_ids),
                failures,
            )
            self._anonymize_ymls(
                submissions_dir,
                consented_ids=roster_consented_ids,
                id_map=roster_id_map,
            )

        if course_folder is not None:
            # A failed input keeps no recorded hash, so the course reads as
            # out of date instead of claiming a copy it does not have.
            written = tuple(
                source
                for source, path in zip(sources, inputs, strict=True)
                if not failures.failed(path)
            )
            note_anonymization(course_folder, written)

        return AnonymizeCourseDatasetResult(
            output_dir=output_dir,
            consent_form=ArtifactReport(
                processed_count=len(consent_form_result.entries),
                skipped_count=consent_form_result.skipped_count,
                excluded_count=consent_result.excluded_count,
            ),
            roster=roster_report or ArtifactReport(),
            gradebook=gradebook_report or ArtifactReport(),
            rubric_assessment=ArtifactReport(
                processed_count=rubric_processed,
                skipped_count=rubric_skipped,
                excluded_count=rubric_excluded,
            ),
            consent_decisions=consent_result.decisions,
            failures=tuple(failures.failures),
        )

    def _write_roster(
        self,
        students: tuple[RosterStudent, ...],
        consented_ids: _Ids,
        id_map: _IdMap,
        output_path: Path,
    ) -> ArtifactReport:
        roster_result = self._anonymize_roster_use_case.execute(
            AnonymizeRosterRequest(
                students=students,
                consented_ids=consented_ids,
                id_map=id_map,
            )
        )

        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow(
                [
                    "ID",
                    "Posting ID",
                    "First Name",
                    "Last Name",
                    "Status",
                    "Units",
                    "Grade Basis",
                    "Program and Plan",
                    "Academic Level",
                    "ASURITE",
                    "Residency",
                    "Zoom Email",
                ]
            )

            for student in roster_result.students:
                writer.writerow(
                    [
                        student.id,
                        student.posting_id,
                        student.first_name,
                        student.last_name,
                        student.status,
                        student.units,
                        student.grade_basis,
                        student.program_and_plan,
                        student.academic_level,
                        student.asurite,
                        student.residency,
                        student.zoom_email,
                    ]
                )

        return ArtifactReport(
            processed_count=len(roster_result.students),
            skipped_count=roster_result.skipped_count,
            excluded_count=roster_result.excluded_count,
        )

    def _write_gradebook(
        self,
        gradebook_path: Path,
        consented_ids: _Ids,
        id_map: _IdMap,
        output_path: Path,
    ) -> ArtifactReport:
        gradebook = self._gradebook_reader.parse(gradebook_path)

        gradebook_result = self._anonymize_gradebook_use_case.execute(
            AnonymizeGradebookRequest(
                gradebook=gradebook,
                consented_ids=consented_ids,
                id_map=id_map,
            )
        )

        assignment_headers = [column.raw_header for column in gradebook_result.gradebook.columns]

        fieldnames = [
            "Student",
            "ID",
            "SIS Login ID",
            "Section",
            *assignment_headers,
        ]

        with output_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
            )

            writer.writeheader()

            manual_posting_row = dict.fromkeys(fieldnames, "")
            manual_posting_row["Student"] = "Manual Posting"
            writer.writerow(manual_posting_row)

            points_row = dict.fromkeys(fieldnames, "")
            points_row["Student"] = "Points Possible"

            for column in gradebook_result.gradebook.columns:
                points_row[column.raw_header] = (
                    "" if column.points_possible is None else column.points_possible
                )

            writer.writerow(points_row)

            for row in gradebook_result.gradebook.rows:
                output_row = {
                    "Student": row.student_name,
                    "ID": row.canvas_id,
                    "SIS Login ID": row.sis_login_id,
                    "Section": row.section,
                }

                for header in assignment_headers:
                    score = row.assignment_scores.get(header)
                    output_row[header] = "" if score is None else score

                writer.writerow(output_row)

        return ArtifactReport(
            processed_count=len(gradebook_result.gradebook.rows),
            skipped_count=gradebook_result.skipped_count,
            excluded_count=gradebook_result.excluded_count,
        )

    def _write_rubric(
        self,
        rubric_path: Path,
        consented_ids: _Ids,
        id_map: _IdMap,
        seed: int | None,
        output_path: Path,
    ) -> AnonymizeRubricAssessmentResult:
        assessments = tuple(self._rubric_reader.read(rubric_path))

        rubric_result = self._anonymize_rubric_use_case.execute(
            AnonymizeRubricAssessmentRequest(
                assessments=assessments,
                consented_ids=consented_ids,
                id_map=id_map,
                seed=seed,
            )
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Carries no student data, so it is copied as-is rather than anonymized.
        definition_path = rubric_path.parent / RUBRIC_DEFINITION_FILE
        if definition_path.exists():
            shutil.copy2(definition_path, output_path.parent / RUBRIC_DEFINITION_FILE)

        payload = [
            {
                "student_id": assessment.student_id,
                "submission_id": assessment.submission_id,
                "criteria": [
                    {
                        "criterion_id": criterion.criterion_id,
                        "points": criterion.points,
                        "comments": criterion.comments,
                    }
                    for criterion in assessment.criteria
                ],
            }
            for assessment in rubric_result.assessments
        ]

        output_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        return rubric_result

    def _anonymize_submissions(
        self,
        submissions_dir: Path,
        output_dir: Path,
        consented_sis_ids: set[int],
        failures: _FailureLog,
    ) -> None:
        for metadata_path in sorted(submissions_dir.rglob("submission_metadata.yml")):
            submissions = failures.attempt(
                self._gradescope_reader.read, metadata_path, inputs=(metadata_path,)
            )
            if submissions is None:
                continue

            extracted_dir = metadata_path.parent
            module_dir = submissions_dir / metadata_path.relative_to(submissions_dir).parts[0]

            for submission in submissions:
                try:
                    sis_id = int(submission.submitter.sid)
                except (TypeError, ValueError):
                    continue

                if sis_id not in consented_sis_ids:
                    continue

                submission_input = extracted_dir / submission.submission_key

                if not submission_input.is_dir():
                    continue

                submission_output = output_dir / module_dir.name / submission.submission_key

                failures.attempt(
                    self._anonymize_gradescope_use_case.execute,
                    AnonymizeGradescopeSubmissionsRequest(
                        input_folder=str(submission_input),
                        output_folder=str(submission_output),
                    ),
                    inputs=(submission_input,),
                    outputs=(submission_output,),
                )

    def _anonymize_ymls(
        self,
        course_folder: Path,
        consented_ids: tuple[int, ...],
        id_map: tuple[tuple[int, int], ...],
    ):
        original_root = course_folder.parent
        anonymized_root = original_root.parent / "anonymized"

        for yml_path in original_root.rglob("submission_metadata.yml"):
            # Path relative to original/
            relative_path = yml_path.relative_to(original_root)

            # Equivalent destination under anonymized/
            output_path = anonymized_root / relative_path
            output_path = output_path.parents[2]
            output_path = output_path / "submission_metadata.yml"

            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            self._anonymize_gradescope_yml_use_case.execute(
                AnonymizeGradescopeYMLRequest(
                    input_YML=yml_path,
                    consented_ids=consented_ids,
                    id_map=id_map,
                    output_YML=output_path,
                )
            )


def _course_folder(snapshot_dir: Path) -> CourseFolder | None:
    """The course folder being anonymized, or None for a folder not named like one.

    The CLI accepts any folder; only workspace course folders have a manifest
    to record into, and only they are shown in the course browser.
    """
    try:
        key = CourseKey.parse(snapshot_dir.name)
    except ValueError:
        return None
    return CourseFolder(snapshot_dir, key)


def build_anonymize_course_dataset_use_case() -> AnonymizeCourseDatasetUseCase:
    """The pipeline wired with GAVEL's own readers and anonymizers."""
    return AnonymizeCourseDatasetUseCase(
        consent_form_reader=CanvasConsentFormCSVReader(),
        downselect_use_case=DownselectConsentedStudentsUseCase(),
        id_map_use_case=GenerateAnonymousIdMapUseCase(),
        roster_reader=CanvasRosterCSVReader(),
        anonymize_roster_use_case=AnonymizeRosterUseCase(),
        gradebook_reader=LegacyGradebookCSVReader(),
        anonymize_gradebook_use_case=AnonymizeGradebookUseCase(),
        anonymize_consent_form_use_case=AnonymizeConsentFormUseCase(),
        rubric_reader=RubricAssessmentJSONReader(),
        anonymize_rubric_use_case=AnonymizeRubricAssessmentUseCase(),
        gradescope_reader=YamlGradescopeReader(),
        anonymize_gradescope_use_case=AnonymizeGradescopeSubmissionsUseCase(),
        anonymize_gradescope_yml_use_case=AnonymizeGradescopeYMLUseCase(),
    )
