import json
from pathlib import Path

import pytest

from GAVEL.app.usecases.anonymize_consent_form import AnonymizeConsentFormUseCase
from GAVEL.app.usecases.anonymize_course_dataset import (
    AnonymizeCourseDatasetRequest,
    AnonymizeCourseDatasetUseCase,
)
from GAVEL.app.usecases.anonymize_gradebook import AnonymizeGradebookUseCase
from GAVEL.app.usecases.anonymize_roster import AnonymizeRosterUseCase
from GAVEL.app.usecases.anonymize_rubric_assessment import (
    AnonymizeRubricAssessmentUseCase,
)
from GAVEL.app.usecases.downselect_consented_students import (
    DownselectConsentedStudentsUseCase,
)
from GAVEL.app.usecases.generate_anonymous_id_map import (
    GenerateAnonymousIdMapUseCase,
)
from GAVEL.infra.csv.canvas_consent_form_csv_reader import (
    CanvasConsentFormCSVReader,
)
from GAVEL.infra.csv.canvas_gradebook_csv_reader import LegacyGradebookCSVReader
from GAVEL.infra.csv.canvas_roster_csv_reader import CanvasRosterCSVReader
from GAVEL.infra.json.rubric_assessment_json_reader import (
    RubricAssessmentJSONReader,
)


@pytest.fixture
def use_case() -> AnonymizeCourseDatasetUseCase:
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
    )


def write_consent_form(snapshot_dir: Path) -> None:
    original_dir = snapshot_dir / "original"
    original_dir.mkdir(parents=True, exist_ok=True)

    consent_path = original_dir / "consent_form.csv"

    consent_path.write_text(
        "sis_id,name,attempt,leave blank if your name is correct,Do you consent\n"
        "100001,Test Student,1,Test Student,True\n",
        encoding="utf-8",
    )


def write_roster(snapshot_dir: Path) -> None:
    roster_path = snapshot_dir / "original" / "roster.csv"

    roster_path.write_text(
        "ID,Posting ID,First Name,Last Name,Status,Units,"
        "Grade Basis,Program and Plan,Academic Level,ASURITE,"
        "Residency,Zoom Email\n"
        "100001,100001-001,Test,Student,Enrolled,3,"
        "GRD,SER,Senior,teststudent,Resident,test@example.com\n",
        encoding="utf-8",
    )


def write_gradebook(snapshot_dir: Path) -> None:
    gradebook_path = snapshot_dir / "original" / "gradebook.csv"

    gradebook_path.write_text(
        "Student,ID,SIS Login ID,Section,Module 1: Assignment (7216983)\n"
        "Manual Posting,,,,\n"
        "Points Possible,,,,10\n"
        '"Test Student",100001,teststudent,SER 401,9\n',
        encoding="utf-8",
    )


def write_rubric(snapshot_dir: Path) -> Path:
    assignment_dir = snapshot_dir / "original" / "assignments" / "7216983_m1"
    assignment_dir.mkdir(parents=True, exist_ok=True)

    rubric_path = assignment_dir / "rubric_assessment_12345_7216983.json"

    rubric_path.write_text(
        json.dumps(
            [
                {
                    "student_id": 100001,
                    "submission_id": 9001,
                    "criteria": [
                        {
                            "criterion_id": "crit_1",
                            "points": 4.0,
                            "comments": "Good work",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    return rubric_path


class TestValidation:
    def test_missing_consent_form_raises_error(
        self,
        use_case,
        tmp_path: Path,
    ):
        original_dir = tmp_path / "original"
        original_dir.mkdir()

        request = AnonymizeCourseDatasetRequest(
            snapshot_dir=tmp_path,
            seed=42,
        )

        with pytest.raises(
            ValueError,
            match="Consent form is missing from the dataset",
        ):
            use_case.execute(request)


class TestMissingArtifacts:
    def test_missing_roster_is_skipped(
        self,
        use_case,
        tmp_path: Path,
    ):
        write_consent_form(tmp_path)

        request = AnonymizeCourseDatasetRequest(
            snapshot_dir=tmp_path,
            seed=42,
        )

        result = use_case.execute(request)

        assert result.roster.processed_count == 0
        assert result.roster.skipped_count == 1
        assert result.roster.excluded_count == 0

    def test_missing_gradebook_is_skipped(
        self,
        use_case,
        tmp_path: Path,
    ):
        write_consent_form(tmp_path)

        request = AnonymizeCourseDatasetRequest(
            snapshot_dir=tmp_path,
            seed=42,
        )

        result = use_case.execute(request)

        assert result.gradebook.processed_count == 0
        assert result.gradebook.skipped_count == 1
        assert result.gradebook.excluded_count == 0

    def test_no_rubric_files_returns_zero_counts(
        self,
        use_case,
        tmp_path: Path,
    ):
        write_consent_form(tmp_path)

        request = AnonymizeCourseDatasetRequest(
            snapshot_dir=tmp_path,
            seed=42,
        )

        result = use_case.execute(request)

        assert result.rubric_assessment.processed_count == 0
        assert result.rubric_assessment.skipped_count == 0
        assert result.rubric_assessment.excluded_count == 0


class TestFullPipeline:
    def test_shared_anonymous_id_across_outputs(
        self,
        use_case,
        tmp_path: Path,
    ):
        write_consent_form(tmp_path)
        write_roster(tmp_path)
        write_gradebook(tmp_path)
        write_rubric(tmp_path)

        request = AnonymizeCourseDatasetRequest(
            snapshot_dir=tmp_path,
            seed=42,
        )

        result = use_case.execute(request)

        output_dir = tmp_path / "anonymized"

        assert (output_dir / "consent_form.csv").exists()
        assert (output_dir / "roster.csv").exists()
        assert (output_dir / "gradebook.csv").exists()

        rubric_output = (
            output_dir / "assignments" / "7216983_m1" / "rubric_assessment_12345_7216983.json"
        )

        assert rubric_output.exists()

        roster_students = CanvasRosterCSVReader().read(output_dir / "roster.csv")
        anonymous_roster_id = int(roster_students[0].id)

        gradebook = LegacyGradebookCSVReader().parse(output_dir / "gradebook.csv")
        anonymous_gradebook_id = gradebook.rows[0].canvas_id

        rubric_data = json.loads(rubric_output.read_text(encoding="utf-8"))
        anonymous_rubric_id = rubric_data[0]["student_id"]

        assert anonymous_roster_id == anonymous_gradebook_id
        assert anonymous_roster_id == anonymous_rubric_id

        assert result.roster.processed_count == 1
        assert result.gradebook.processed_count == 1
        assert result.rubric_assessment.processed_count == 1
