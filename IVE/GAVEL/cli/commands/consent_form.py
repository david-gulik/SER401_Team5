from __future__ import annotations

import sys
from argparse import Namespace

from GAVEL.app.usecases.download_consent_form import (
    DownloadConsentFormRequest,
    DownloadConsentFormUseCase,
)
from GAVEL.app.workspace.recording import ArtifactExistsError
from GAVEL.app_context import AppContext
from GAVEL.cli.commands.workspace_args import resolve_course_folder


def handle_consent_form_download(ctx: AppContext, args: Namespace) -> int:
    try:
        course_id = int(args.course_id)
        quiz_id = int(args.quiz_id)
    except (TypeError, ValueError):
        print("course_id and quiz_id must be valid integers.", file=sys.stderr)
        return 2

    folder = resolve_course_folder(ctx, args, course_id=course_id)
    if folder is None:
        return 2

    try:
        print(f"[CONSENT_FORM] Downloading consent form for course={course_id}, quiz={quiz_id}...")
        result = DownloadConsentFormUseCase(ctx.services.canvas_client).execute(
            DownloadConsentFormRequest(
                course_id=course_id, quiz_id=quiz_id, folder=folder, overwrite=args.overwrite
            )
        )
    except ArtifactExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"[CONSENT_FORM] {result.message}")
    return 0
