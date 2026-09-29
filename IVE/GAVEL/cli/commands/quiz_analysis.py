from __future__ import annotations

import sys
from argparse import Namespace

from GAVEL.app.usecases.download_all_quizzes import (
    DownloadAllQuizzesRequest,
    DownloadAllQuizzesUseCase,
)
from GAVEL.app_context import AppContext
from GAVEL.cli.commands.workspace_args import resolve_course_folder


def handle_quiz_analysis_download(ctx: AppContext, args: Namespace) -> int:
    try:
        course_id = int(args.course_id)
    except (TypeError, ValueError):
        print("course_id must be a valid integer.", file=sys.stderr)
        return 2

    folder = resolve_course_folder(ctx, args, course_id=course_id)
    if folder is None:
        return 2

    try:
        print(f"[QUIZ] Downloading student analysis for course={course_id}...")
        result = DownloadAllQuizzesUseCase(ctx.services.canvas_client).execute(
            DownloadAllQuizzesRequest(course_id=course_id, folder=folder, overwrite=args.overwrite)
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
