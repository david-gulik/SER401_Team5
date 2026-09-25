from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.usecases.generate_anonymous_id_map import (
    GenerateAnonymousIdMapRequest,
    GenerateAnonymousIdMapUseCase,
)

from GAVEL.app.usecases.anonymize_consent_form import (
    AnonymizeConsentFormRequest,
    AnonymizeConsentFormUseCase,
)
from GAVEL.app.usecases.anonymize_gradebook import (
    AnonymizeGradebookRequest,
    AnonymizeGradebookUseCase,
)
from GAVEL.app.usecases.anonymize_roster import (
    AnonymizeRosterRequest,
    AnonymizeRosterUseCase,
)
from GAVEL.app.usecases.anonymize_rubric_assessment import (
    AnonymizeRubricAssessmentRequest,
    AnonymizeRubricAssessmentUseCase,
)
from GAVEL.app.usecases.downselect_consented_students import (
    DownselectConsentedStudentsRequest,
    DownselectConsentedStudentsUseCase,
)
from GAVEL.infra.csv.canvas_consent_form_csv_reader import (
    CanvasConsentFormCSVReader,
)
from GAVEL.infra.csv.canvas_gradebook_csv_reader import LegacyGradebookCSVReader
from GAVEL.infra.csv.canvas_roster_csv_reader import CanvasRosterCSVReader
from GAVEL.infra.json.rubric_assessment_json_reader import (
    RubricAssessmentJSONReader,
)


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

    def execute(
        self,
        request: AnonymizeCourseDatasetRequest,
    ) -> AnonymizeCourseDatasetResult:
        original_dir = request.snapshot_dir / "original"
        output_dir = request.snapshot_dir / "anonymized"
        output_dir.mkdir(parents=True, exist_ok=True)
        consent_form_path = original_dir / "consent_form.csv"
        roster_path = original_dir / "roster.csv"
        gradebook_path = original_dir / "gradebook.csv"
        assignments_dir = original_dir / "assignments"

        if not consent_form_path.exists():
            raise ValueError("Consent form is missing from the dataset")

        consent_entries = tuple(self._consent_form_reader.read(str(consent_form_path)))

        consent_result = self._downselect_use_case.execute(
            DownselectConsentedStudentsRequest(
                entries=consent_entries,
            )
        )

        id_map_result = self._id_map_use_case.execute(
            GenerateAnonymousIdMapRequest(
                student_ids=set(consent_result.consented_ids),
                seed=request.seed,
            )
        )

        id_map = tuple(id_map_result.id_map.items())

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
        if roster_path.exists():
            roster_students = tuple(self._roster_reader.read(roster_path))

            roster_result = self._anonymize_roster_use_case.execute(
                AnonymizeRosterRequest(
                    students=roster_students,
                    consented_ids=consent_result.consented_ids,
                    id_map=id_map,
                )
            )

            roster_output_path = output_dir / "roster.csv"

            with roster_output_path.open("w", newline="", encoding="utf-8") as f:
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

            roster_report = ArtifactReport(
                processed_count=len(roster_result.students),
                skipped_count=roster_result.skipped_count,
                excluded_count=roster_result.excluded_count,
            )

        else:
            roster_report = ArtifactReport(
                skipped_count=1,
            )

        if gradebook_path.exists():
            gradebook = self._gradebook_reader.parse(gradebook_path)

            gradebook_result = self._anonymize_gradebook_use_case.execute(
                AnonymizeGradebookRequest(
                    gradebook=gradebook,
                    consented_ids=consent_result.consented_ids,
                    id_map=id_map,
                )
            )

            gradebook_output_path = output_dir / "gradebook.csv"

            assignment_headers = [
                column.raw_header for column in gradebook_result.gradebook.columns
            ]

            fieldnames = [
                "Student",
                "ID",
                "SIS Login ID",
                "Section",
                *assignment_headers,
            ]

            with gradebook_output_path.open(
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

            gradebook_report = ArtifactReport(
                processed_count=len(gradebook_result.gradebook.rows),
                skipped_count=gradebook_result.skipped_count,
                excluded_count=gradebook_result.excluded_count,
            )

        else:
            gradebook_report = ArtifactReport(
                skipped_count=1,
            )

        rubric_files = list(assignments_dir.rglob("rubric_assessment_*.json"))

        rubric_results = []

        for rubric_path in rubric_files:
            assessments = tuple(self._rubric_reader.read(rubric_path))

            rubric_result = self._anonymize_rubric_use_case.execute(
                AnonymizeRubricAssessmentRequest(
                    assessments=assessments,
                    consented_ids=consent_result.consented_ids,
                    id_map=id_map,
                )
            )

            relative_path = rubric_path.relative_to(assignments_dir)

            rubric_output_path = output_dir / "assignments" / relative_path

            rubric_output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

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

            rubric_output_path.write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )

            rubric_results.append((rubric_path, rubric_result))

        rubric_skipped = sum(result.skipped_count for _, result in rubric_results)

        rubric_excluded = sum(result.excluded_count for _, result in rubric_results)

        rubric_processed = sum(len(result.assessments) for _, result in rubric_results)

        return AnonymizeCourseDatasetResult(
            output_dir=output_dir,
            consent_form=ArtifactReport(
                processed_count=len(consent_form_result.entries),
                skipped_count=consent_form_result.skipped_count,
                excluded_count=consent_result.excluded_count,
            ),
            roster=roster_report,
            gradebook=gradebook_report,
            rubric_assessment=ArtifactReport(
                processed_count=rubric_processed,
                skipped_count=rubric_skipped,
                excluded_count=rubric_excluded,
            ),
        )
