from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Optional

from GAVEL.app_context import AppContext
from GAVEL.app_services import AppServices
from GAVEL.bootstrap import build_canvas_client, build_roster_client
from GAVEL.cli.commands.canvas_course import handle_canvas_course_download
from GAVEL.cli.commands.roster import handle_roster_download, handle_roster_list_terms
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

    # -- roster commands ----------------------------------------------------
    roster_parser = subparsers.add_parser("roster", help="ASU roster operations")
    roster_subparsers = roster_parser.add_subparsers(dest="roster_command", required=True)

    # roster list-terms
    terms_parser = roster_subparsers.add_parser("list-terms", help="List available academic terms")
    terms_parser.set_defaults(handler=handle_roster_list_terms)

    # roster download
    roster_dl = roster_subparsers.add_parser("download", help="Download a roster CSV")
    roster_dl.add_argument("--term", required=True, help="ASU term code (e.g. '2261')")
    roster_dl.add_argument("--class-number", help="Five-digit class number (direct mode)")
    roster_dl.add_argument("--subject", help="Subject prefix for catalog lookup (e.g. 'SER')")
    roster_dl.add_argument("--catalog-number", help="Catalog number for lookup (e.g. '222')")
    roster_dl.add_argument("--info-only", action="store_true", help="Show class info only, skip download")
    roster_dl.add_argument("--output", "-o", help="Save CSV to this file (default: stdout)")
    roster_dl.set_defaults(handler=handle_roster_download)

    return parser


def _build_app_context() -> AppContext:
    root = Path(__file__).resolve().parents[1]
    tokens_path = root / "theme" / "tokens_dark.json"
    tokens = load_tokens(tokens_path)
    theme = ThemeContext(tokens=tokens)

    config_service = ConfigService()
    logger = AppLogger(name="my_app.cli")

    canvas_client = build_canvas_client(config_service.get(), logger)
    roster_client = build_roster_client(config_service.get(), logger)
    services = AppServices.build(canvas_client, roster_client, logger)

    return AppContext(
        theme=theme,
        config=config_service,
        logger=logger,
        services=services,
    )


if __name__ == "__main__":
    sys.exit(main())
