from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from GAVEL.app_context import AppContext
from GAVEL.app_services import AppServices
from GAVEL.bootstrap import build_canvas_client, build_roster_client
from GAVEL.cli.commands.canvas_course import handle_canvas_course_download
from GAVEL.cli.commands.canvas_gradebook import handle_canvas_gradebook_download
from GAVEL.cli.commands.gradescope_download import handle_gradescope_download
from GAVEL.cli.commands.quiz_analysis import handle_quiz_analysis_download
from GAVEL.cli.commands.roster import handle_roster_download, handle_roster_list_terms
from GAVEL.services.config_service import ConfigService
from GAVEL.services.logger import AppLogger
from GAVEL.theme.context import ThemeContext
from GAVEL.theme.tokens import load_tokens


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    ctx = _build_app_context()

    handler: Callable[[AppContext, argparse.Namespace], int] = args.handler
    return handler(ctx, args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ExtendableUI CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    canvas_parser = subparsers.add_parser("canvas-course", help="Canvas course operations")
    canvas_subparsers = canvas_parser.add_subparsers(dest="canvas_command", required=True)

    download_parser = canvas_subparsers.add_parser("download", help="Download Canvas course data")
    download_parser.add_argument(
        "--course-id", required=True, help="Canvas course numeric identifier"
    )
    download_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the JSON course data will be written",
    )
    download_parser.set_defaults(handler=handle_canvas_course_download)

    gradebook_parser = subparsers.add_parser("canvas-gradebook", help="Canvas gradebook operations")
    gradebook_subparsers = gradebook_parser.add_subparsers(dest="gradebook_command", required=True)

    gradebook_download_parser = gradebook_subparsers.add_parser(
        "download", help="Download Canvas gradebook CSV"
    )
    gradebook_download_parser.add_argument(
        "--course-id", required=True, help="Canvas course numeric identifier"
    )
    gradebook_download_parser.add_argument(
        "--output", required=True, help="Path where the CSV file will be written"
    )
    gradebook_download_parser.set_defaults(handler=handle_canvas_gradebook_download)

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
    roster_dl.add_argument(
        "--info-only", action="store_true", help="Show class info only, skip download"
    )
    roster_dl.add_argument("--output", "-o", help="Save CSV to this file (default: stdout)")
    roster_dl.set_defaults(handler=handle_roster_download)

    # quiz commands
    quiz_parser = subparsers.add_parser("quiz", help="Canvas quiz operations")
    quiz_subparsers = quiz_parser.add_subparsers(dest="quiz_command", required=True)

    # quiz download
    quiz_dl = quiz_subparsers.add_parser("download", help="Download a quiz student analysis CSV")
    quiz_dl.add_argument("--course-id", required=True, help="Canvas course numeric identifier")
    quiz_dl.add_argument("--quiz-id", required=True, help="Canvas quiz numeric identifier")
    quiz_dl.add_argument("--output", "-o", help="Save CSV to this file (default: stdout)")
    quiz_dl.set_defaults(handler=handle_quiz_analysis_download)

    # Gradescope downloader parser
    gradescope_parser = subparsers.add_parser("gradescope", help="Gradescope Submission Downloader")
    gradescope_subparsers = gradescope_parser.add_subparsers(dest="gradescope_command", required=True)

    gradescope_dl = gradescope_subparsers.add_parser(
        "download", help="Download all Gradescope assignment submissions for a given Canvas course"
    )
    gradescope_dl.add_argument("--course-id", required=True)
    gradescope_dl.add_argument(
        "--show-browser",
        action="store_true",
        help="Show Chrome instead of running headless",
    )
    gradescope_dl.set_defaults(handler=handle_gradescope_download)


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
