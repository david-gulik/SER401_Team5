from __future__ import annotations

import sys
from argparse import Namespace

from GAVEL.app.usecases.download_gradebook import (
    DownloadGradebookRequest,
    DownloadGradebookUseCase,
)
from GAVEL.app.workspace.recording import ArtifactExistsError
from GAVEL.app_context import AppContext
from GAVEL.cli.commands.workspace_args import resolve_course_folder


def handle_canvas_gradebook_download(ctx: AppContext, args: Namespace) -> int:
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

    try:
        result = DownloadGradebookUseCase(ctx.services.canvas_client).execute(
            DownloadGradebookRequest(course_id=course_id, folder=folder, overwrite=args.overwrite)
        )
    except ArtifactExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Canvas gradebook download failed: {exc}")
        print(f"Failed to download gradebook CSV: {exc}", file=sys.stderr)
        return 1

    print(result.message)
    return 0
