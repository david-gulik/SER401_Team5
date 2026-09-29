"""The ``--workspace`` / ``--course-folder`` arguments every download command shares.

A download lands in ``<workspace>/courses/<course folder>/``. Canvas commands
can work out the course folder from ``--course-id`` (the Canvas course code
carries subject, term, session and class number); everything else needs
``--course-folder`` spelled out. See ``docs/workspace_layout.md``.
"""

from __future__ import annotations

import os
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app_context import AppContext


def default_workspace_root() -> Path:
    env_dir = (os.getenv("DEFAULT_OUTPUT_DIR") or "").strip()
    return Path(env_dir).expanduser() if env_dir else Path.home() / "Downloads" / "GAVEL"


def add_workspace_arguments(
    parser: ArgumentParser, *, course_folder_required: bool = False
) -> None:
    parser.add_argument(
        "--workspace",
        help="Workspace root (default: DEFAULT_OUTPUT_DIR from .env, else ~/Downloads/GAVEL)",
    )
    parser.add_argument(
        "--course-folder",
        required=course_folder_required,
        help=(
            "Course folder name such as ser222_25sc_12345. Canvas commands derive it from "
            "--course-id when omitted."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace files that were already downloaded into the course folder",
    )


def workspace_from_args(args: Namespace) -> Workspace:
    root = getattr(args, "workspace", None)
    return Workspace(Path(root).expanduser() if root else default_workspace_root())


def resolve_course_folder(
    ctx: AppContext, args: Namespace, *, course_id: int | None = None
) -> CourseFolder | None:
    """The course folder a command should write to, or None after printing why not."""
    workspace = workspace_from_args(args)

    name = (getattr(args, "course_folder", None) or "").strip()
    if name:
        try:
            key = CourseKey.parse(name)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return None
        return workspace.course(key)

    if course_id is None:
        print("Error: --course-folder is required for this command.", file=sys.stderr)
        return None

    try:
        data = ctx.services.canvas_client.fetch_course_data(course_id)
    except Exception as exc:  # noqa: BLE001
        print(
            f"Error: could not look up Canvas course {course_id} to name the course folder "
            f"({exc}). Pass --course-folder explicitly.",
            file=sys.stderr,
        )
        return None

    key = CourseKey.from_canvas_course_code(data.course.course_code)
    if key is None:
        print(
            f"Error: Canvas course '{data.course.name}' has no ASU course code to name the "
            "course folder from. Pass --course-folder explicitly.",
            file=sys.stderr,
        )
        return None
    return workspace.course(key)
