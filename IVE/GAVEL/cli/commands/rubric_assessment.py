from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

from GAVEL.app.usecases.download_rubric_assessment import (
    DownloadRubricAssessmentRequest,
    DownloadRubricAssessmentUseCase,
)
from GAVEL.app_context import AppContext


def handle_rubric_assessment_download(ctx: AppContext, args: Namespace) -> int:
    try:
        print(
            f"[RUBRIC] Downloading rubric assessments for course={args.course_id}, assignment={args.assignment_id}..."
        )
        use_case = DownloadRubricAssessmentUseCase(ctx.services.canvas_client)
        result = use_case.execute(
            DownloadRubricAssessmentRequest(
                course_id=int(args.course_id),
                assignment_id=int(args.assignment_id),
                output_dir=Path(args.output) if args.output else Path("."),
            )
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"[RUBRIC] {result.message}")
    return 0
