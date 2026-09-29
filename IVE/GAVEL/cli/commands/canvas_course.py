from __future__ import annotations

import sys
from argparse import Namespace

from GAVEL.app.usecases.canvas_download_course import DownloadCourseDataRequest
from GAVEL.app_context import AppContext
from GAVEL.cli.commands.workspace_args import resolve_course_folder


def handle_canvas_course_download(ctx: AppContext, args: Namespace) -> int:
    try:
        course_id = int(args.course_id)
    except (TypeError, ValueError):
        print("course_id must be a valid integer.", file=sys.stderr)
        return 2

    if course_id <= 0:
        print("course_id must be greater than zero.", file=sys.stderr)
        return 2

    folder = resolve_course_folder(ctx, args, course_id=course_id)
    if folder is None:
        return 2

    request = DownloadCourseDataRequest(course_id=course_id, folder=folder)

    try:
        result = ctx.services.download_course_data_uc.execute(request)
    except ValueError as exc:
        print(f"Invalid request: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Canvas course download failed: {exc}")
        print(f"Failed to download course: {exc}", file=sys.stderr)
        return 1

    print(result.message)
    return 0
