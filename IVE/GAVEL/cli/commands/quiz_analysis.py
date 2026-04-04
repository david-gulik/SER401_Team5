from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

from GAVEL.app_context import AppContext


def handle_quiz_analysis_download(ctx: AppContext, args: Namespace) -> int:
    try:
        print(
            f"[QUIZ] Downloading student analysis for course={args.course_id}, quiz={args.quiz_id}..."
        )
        csv_bytes = ctx.services.canvas_client.fetch_quiz_student_analysis(
            int(args.course_id), int(args.quiz_id)
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_bytes(csv_bytes)
        print(f"[QUIZ] Saved to {args.output}")
    else:
        sys.stdout.buffer.write(csv_bytes)

    return 0
