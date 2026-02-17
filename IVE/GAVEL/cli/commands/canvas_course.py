from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from GAVEL.app.usecases.canvas_download_course import DownloadCourseDataRequest
from GAVEL.app_context import AppContext


def handle_canvas_course_download(ctx: AppContext, args: Namespace) -> int:
    try:
        course_id = int(args.course_id)
    except (TypeError, ValueError):
        print("course_id must be a valid integer.")
        return 2

    if course_id <= 0:
        print("course_id must be greater than zero.")
        return 2

    output_dir = Path(args.output_dir).expanduser()

    request = DownloadCourseDataRequest(course_id=course_id, output_dir=output_dir)

    try:
        result = ctx.services.download_course_data_uc.execute(request)
    except ValueError as exc:
        print(f"Invalid request: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Canvas course download failed: {exc}")
        print(f"Failed to download course: {exc}")
        return 1

    print(result.message)
    return 0
