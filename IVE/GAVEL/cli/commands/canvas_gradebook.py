from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from GAVEL.app_context import AppContext


def handle_canvas_gradebook_download(ctx: AppContext, args: Namespace) -> int:
    try:
        course_id = int(args.course_id)
    except (TypeError, ValueError):
        print("course_id must be a valid integer.")
        return 2

    if course_id <= 0:
        print("course_id must be greater than zero.")
        return 2

    output_path = Path(args.output).expanduser()

    try:
        csv_bytes = ctx.services.canvas_client.fetch_gradebook_csv(course_id)
        output_path.write_bytes(csv_bytes)
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error(f"Canvas gradebook download failed: {exc}")
        print(f"Failed to download gradebook CSV: {exc}")
        return 1

    print(f"Gradebook CSV saved to {output_path}")
    return 0