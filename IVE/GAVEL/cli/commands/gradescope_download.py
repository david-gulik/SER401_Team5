from __future__ import annotations

import sys
from argparse import Namespace

from GAVEL.app.usecases.download_gradescope_submissions import (
    DownloadGradescopeSubmissionsRequest,
    DownloadGradescopeSubmissionsUseCase,
)
from GAVEL.app.workspace.recording import ArtifactExistsError
from GAVEL.app_context import AppContext
from GAVEL.cli.commands.workspace_args import resolve_course_folder


def handle_gradescope_download(ctx: AppContext, args: Namespace) -> int:
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
        result = DownloadGradescopeSubmissionsUseCase(
            ctx.services.canvas_client, browser=ctx.services.asu_browser
        ).execute(
            DownloadGradescopeSubmissionsRequest(
                course_id=course_id,
                folder=folder,
                headless=not args.show_browser,
                overwrite=args.overwrite,
            )
        )
    except ArtifactExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Gradescope download failed: {exc}")
        print(f"Failed to download Gradescope submissions: {exc}", file=sys.stderr)
        return 1

    for artifact in result.artifacts:
        where = (
            f"module {artifact.module_number}"
            if artifact.module_number is not None
            else "unmatched"
        )
        print(f"[GRADESCOPE] {artifact.kind} '{artifact.gradescope_name}' -> {where}")
    print(result.message)
    return 0
