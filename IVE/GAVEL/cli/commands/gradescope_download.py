from __future__ import annotations

import sys
from argparse import Namespace
import os
from pathlib import Path

from GAVEL.app_context import AppContext
from GAVEL.app.ports.gradescope_client import GradescopeClient

def handle_gradescope_download(ctx: AppContext, args: Namespace) -> int:
    try:
        course_id = int(args.course_id)
    except (TypeError, ValueError):
        print("course_id must be a valid integer.", file=sys.stderr)
        return 2

    if course_id <= 0:
        print("course_id must be greater than zero.", file=sys.stderr)
        return 2

    username = os.getenv("CANVAS_USERNAME")
    password = os.getenv("CANVAS_PASSWORD")

    if not username or not password:
        print("Environment variables CANVAS_USERNAME and CANVAS_PASSWORD are required.", file=sys.stderr)
        return 2

    try:
        client = GradescopeClient(
            course_url=f"https://canvas.asu.edu/courses/{course_id}",
            headless=False
        )

        client.download_all_assignments(
            username=username,
            password=password
        )

    except Exception as exc:
        ctx.logger.error(f"Gradescope download failed: {exc}")
        print(f"Failed to download Gradescope submissions: {exc}", file=sys.stderr)
        return 1

    print("Gradescope submissions downloaded successfully.")
    return 0
