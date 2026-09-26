from __future__ import annotations

import sys
from argparse import Namespace

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.usecases.download_all_rubric_assessments import (
    DownloadAllRubricAssessmentsRequest,
    DownloadAllRubricAssessmentsUseCase,
)
from GAVEL.app.usecases.download_rubric_assessment import (
    DownloadRubricAssessmentRequest,
    DownloadRubricAssessmentUseCase,
)
from GAVEL.app.workspace.recording import ArtifactExistsError
from GAVEL.app_context import AppContext
from GAVEL.cli.commands.workspace_args import resolve_course_folder


def _assignment(ctx: AppContext, course_id: int, assignment_id: int) -> CanvasAssignment:
    """The assignment with its Canvas name when the list is reachable, else id only."""
    try:
        for assignment in ctx.services.canvas_client.list_assignments(course_id):
            if assignment.id == assignment_id:
                return assignment
    except Exception:  # noqa: BLE001 - the name only affects the folder tag
        pass
    return CanvasAssignment(id=assignment_id, name="")


def handle_rubric_assessment_download(ctx: AppContext, args: Namespace) -> int:
    try:
        course_id = int(args.course_id)
        assignment_id = int(args.assignment_id)
    except (TypeError, ValueError):
        print("course_id and assignment_id must be valid integers.", file=sys.stderr)
        return 2

    folder = resolve_course_folder(ctx, args, course_id=course_id)
    if folder is None:
        return 2

    try:
        print(
            f"[RUBRIC] Downloading rubric assessments for course={course_id}, "
            f"assignment={assignment_id}..."
        )
        result = DownloadRubricAssessmentUseCase(ctx.services.canvas_client).execute(
            DownloadRubricAssessmentRequest(
                course_id=course_id,
                assignment=_assignment(ctx, course_id, assignment_id),
                folder=folder,
                overwrite=args.overwrite,
            )
        )
    except ArtifactExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"[RUBRIC] {result.message}")
    return 0


def handle_rubric_assessment_download_all(ctx: AppContext, args: Namespace) -> int:
    try:
        course_id = int(args.course_id)
    except (TypeError, ValueError):
        print("course_id must be a valid integer.", file=sys.stderr)
        return 2

    folder = resolve_course_folder(ctx, args, course_id=course_id)
    if folder is None:
        return 2

    try:
        print(
            f"[RUBRIC] Downloading rubric assessments for every assignment in course={course_id}..."
        )
        result = DownloadAllRubricAssessmentsUseCase(ctx.services.canvas_client).execute(
            DownloadAllRubricAssessmentsRequest(
                course_id=course_id, folder=folder, overwrite=args.overwrite
            )
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for outcome in result.failed:
        print(
            f"[RUBRIC] FAILED {outcome.assignment_name} ({outcome.assignment_id}): {outcome.error}",
            file=sys.stderr,
        )
    for outcome in result.already_downloaded:
        print(
            f"[RUBRIC] ALREADY DOWNLOADED {outcome.assignment_name} ({outcome.assignment_id})",
            file=sys.stderr,
        )
    print(
        f"[RUBRIC] {len(result.succeeded)} succeeded, {len(result.skipped)} skipped, "
        f"{len(result.already_downloaded)} already downloaded, {len(result.failed)} failed"
    )
    return 0
