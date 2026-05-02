from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

from GAVEL.app.usecases.download_course_dataset import (
    DownloadCourseDatasetRequest,
    DownloadCourseDatasetUseCase,
)
from GAVEL.app_context import AppContext


def handle_canvas_course_dataset_download(ctx: AppContext, args: Namespace) -> int:
    try:
        course_id = args.course_id
        quiz_id = args.quiz_id
    except (TypeError, ValueError):
        print("course_id and quiz_id must be valid integers.", file=sys.stderr)
        return 2

    if course_id <= 0:
        print("course_id must be greater than zero.", file=sys.stderr)
        return 2

    if quiz_id <= 0:
        print("quiz_id must be greater than zero.", file=sys.stderr)
        return 2

    assignment_ids = (
        [int(x.strip()) for x in args.assignment_ids.split(",") if x.strip()]
        if args.assignment_ids
        else []
    )

    output_dir = Path(args.output_dir).expanduser()

    request = DownloadCourseDatasetRequest(
        course_id=course_id,
        quiz_id=quiz_id,
        assignment_ids=assignment_ids,
        output_dir=output_dir,
    )

    try:
        use_case = DownloadCourseDatasetUseCase(ctx.services.canvas_client)
        result = use_case.execute(request)
    except ValueError as exc:
        print(f"Invalid request: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Dataset download failed: {exc}")
        print(f"Failed to download dataset: {exc}", file=sys.stderr)
        return 1

    print(result.message)
    return 0
