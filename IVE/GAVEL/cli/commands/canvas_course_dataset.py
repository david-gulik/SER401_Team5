from __future__ import annotations

import sys
from argparse import Namespace

from GAVEL.app.usecases.download_course_dataset import (
    DownloadCourseDatasetRequest,
    DownloadCourseDatasetUseCase,
)
from GAVEL.app_context import AppContext
from GAVEL.cli.commands.workspace_args import resolve_course_folder


def handle_canvas_course_dataset_download(ctx: AppContext, args: Namespace) -> int:
    course_id = args.course_id
    quiz_id = args.quiz_id

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

    folder = resolve_course_folder(ctx, args, course_id=course_id)
    if folder is None:
        return 2
    print(f"[DATASET] Course folder: {folder.path}")

    request = DownloadCourseDatasetRequest(
        course_id=course_id,
        quiz_id=quiz_id,
        assignment_ids=assignment_ids,
        folder=folder,
        overwrite=args.overwrite,
    )

    try:
        result = DownloadCourseDatasetUseCase(ctx.services.canvas_client).execute(request)
    except ValueError as exc:
        print(f"Invalid request: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Dataset download failed: {exc}")
        print(f"Failed to download dataset: {exc}", file=sys.stderr)
        return 1

    for outcome in result.outcomes:
        stream = sys.stderr if outcome.status == "failed" else sys.stdout
        print(f"[DATASET] {outcome.step}: {outcome.status} - {outcome.detail}", file=stream)
    print(result.message)
    return 1 if result.failed and not result.succeeded else 0
