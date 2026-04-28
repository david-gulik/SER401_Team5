from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

from GAVEL.app.usecases.download_consent_form import (
    DownloadConsentFormRequest,
    DownloadConsentFormUseCase,
)
from GAVEL.app_context import AppContext


def handle_consent_form_download(ctx: AppContext, args: Namespace) -> int:
    try:
        print(
            f"[CONSENT_FORM] Downloading consent form for course={args.course_id}, quiz={args.quiz_id}..."
        )
        use_case = DownloadConsentFormUseCase(ctx.services.canvas_client)
        result = use_case.execute(
            DownloadConsentFormRequest(
                course_id=int(args.course_id),
                quiz_id=int(args.quiz_id),
                output_dir=Path(args.output),
            )
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"[CONSENT_FORM] {result.message}")
    return 0
