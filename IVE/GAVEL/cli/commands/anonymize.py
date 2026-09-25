from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

from GAVEL.app.usecases.anonymize_course_dataset import (
    AnonymizeCourseDatasetRequest,
    AnonymizeCourseDatasetUseCase,
)
from GAVEL.infra.json.rubric_assessment_json_reader import (
    RubricAssessmentJSONReader,
)

from GAVEL.app.usecases.anonymize_consent_form import AnonymizeConsentFormUseCase
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
from GAVEL.app_context import AppContext
from GAVEL.infra.csv.canvas_consent_form_csv_reader import (
    CanvasConsentFormCSVReader,
)
from GAVEL.infra.csv.canvas_gradebook_csv_reader import LegacyGradebookCSVReader
from GAVEL.infra.csv.canvas_roster_csv_reader import CanvasRosterCSVReader


def handle_anonymize_run(ctx: AppContext, args: Namespace) -> int:
    dataset_dir = Path(args.dataset_dir).expanduser()

    if not dataset_dir.exists():
        print(
            f"Dataset directory does not exist: {dataset_dir}",
            file=sys.stderr,
        )
        return 2

    if not dataset_dir.is_dir():
        print(
            f"Dataset path is not a directory: {dataset_dir}",
            file=sys.stderr,
        )
        return 2

    use_case = AnonymizeCourseDatasetUseCase(
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

    try:
        result = use_case.execute(
            AnonymizeCourseDatasetRequest(
                snapshot_dir=dataset_dir,
            )
        )
    except ValueError as exc:
        print(f"Invalid dataset: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Dataset anonymization failed: {exc}")
        print(
            f"Failed to anonymize dataset: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"Anonymized dataset written to {result.output_dir}")
    print(
        f"Consent form: "
        f"{result.consent_form.processed_count} processed, "
        f"{result.consent_form.skipped_count} skipped, "
        f"{result.consent_form.excluded_count} excluded"
    )
    print(
        f"Roster: "
        f"{result.roster.processed_count} processed, "
        f"{result.roster.skipped_count} skipped, "
        f"{result.roster.excluded_count} excluded"
    )
    print(
        f"Gradebook: "
        f"{result.gradebook.processed_count} processed, "
        f"{result.gradebook.skipped_count} skipped, "
        f"{result.gradebook.excluded_count} excluded"
    )
    print(
        f"Rubric assessments: "
        f"{result.rubric_assessment.processed_count} processed, "
        f"{result.rubric_assessment.skipped_count} skipped, "
        f"{result.rubric_assessment.excluded_count} excluded"
    )

    return 0
