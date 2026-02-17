from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Optional

from GAVEL.app_context import AppContext
from GAVEL.app_services import AppServices
from GAVEL.bootstrap import build_canvas_client
from GAVEL.cli.commands.canvas_course import handle_canvas_course_download
from GAVEL.services.config_service import ConfigService
from GAVEL.services.logger import AppLogger
from GAVEL.theme.context import ThemeContext
from GAVEL.theme.tokens import load_tokens


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    ctx = _build_app_context()

    handler: Callable[[AppContext, argparse.Namespace], int] = getattr(args, "handler")
    return handler(ctx, args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ExtendableUI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    canvas_parser = subparsers.add_parser("canvas-course", help="Canvas course operations")
    canvas_subparsers = canvas_parser.add_subparsers(dest="canvas_command", required=True)

    download_parser = canvas_subparsers.add_parser("download", help="Download Canvas course data")
    download_parser.add_argument("--course-id", required=True, help="Canvas course numeric identifier")
    download_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the JSON course data will be written",
    )
    download_parser.set_defaults(handler=handle_canvas_course_download)

    return parser


def _build_app_context() -> AppContext:
    root = Path(__file__).resolve().parents[1]
    tokens_path = root / "theme" / "tokens_dark.json"
    tokens = load_tokens(tokens_path)
    theme = ThemeContext(tokens=tokens)

    config_service = ConfigService()
    logger = AppLogger(name="my_app.cli")

    canvas_client = build_canvas_client(config_service.get(), logger)
    services = AppServices.build(canvas_client, logger)

    return AppContext(
        theme=theme,
        config=config_service,
        logger=logger,
        services=services,
    )


if __name__ == "__main__":
    sys.exit(main())
