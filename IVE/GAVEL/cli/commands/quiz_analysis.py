from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

from GAVEL.app_context import AppContext
from GAVEL.app.usecases.download_all_quizzes import (
    DownloadAllQuizzesRequest,
    DownloadAllQuizzesUseCase,
)


def handle_quiz_analysis_download(ctx: AppContext, args: Namespace) -> int:
    try:
        print(f"[QUIZ] Downloading student analysis for course={args.course_id}...")
        output_dir = Path(args.output)

        result = DownloadAllQuizzesUseCase(ctx.services.canvas_client).execute(
            DownloadAllQuizzesRequest(
                course_id=int(args.course_id),
                output_dir=output_dir,
            )
        )

    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for outcome in result.succeeded:
        print(f"[QUIZ] Saved '{outcome.quiz_name}' (ID {outcome.quiz_id}) to {outcome.saved_path}")

    for outcome in result.skipped:
        print(
            f"[QUIZ] Warning: skipped "
            f"'{outcome.quiz_name}' (ID {outcome.quiz_id}): "
            f"{outcome.skipped_reason}",
            file=sys.stderr,
        )

    for outcome in result.failed:
        print(
            f"[QUIZ] Warning: could not download "
            f"'{outcome.quiz_name}' (ID {outcome.quiz_id}): {outcome.error}",
            file=sys.stderr,
        )

    print(
        f"[QUIZ] Done. "
        f"{len(result.succeeded)} succeeded, "
        f"{len(result.skipped)} skipped, "
        f"{len(result.failed)} failed."
    )

    return 0
