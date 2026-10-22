from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

from GAVEL.app.dtos.consent_decision import ConsentStatus
from GAVEL.app.usecases.anonymize_course_dataset import (
    AnonymizeCourseDatasetRequest,
    build_anonymize_course_dataset_use_case,
)
from GAVEL.app_context import AppContext


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

    use_case = build_anonymize_course_dataset_use_case()

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

    # Counts only; student names stay out of terminal output.
    status_counts = ", ".join(
        f"{sum(1 for d in result.consent_decisions if d.status is status)} "
        f"{status.value.replace('_', ' ')}"
        for status in ConsentStatus
    )
    print(f"Consent filtering: {status_counts}")

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
