"""Gradescope bulk exports into ``original/assignments/<id>_m<n>/``.

The Gradescope scraper only knows Gradescope's assignment names and writes
``<name>.zip`` and ``<name>_autograder.zip`` into one folder. This use case
lets it write into a staging folder, then files each zip under the Canvas
assignment whose name matches. Anything it cannot match goes to
``assignments/_unmatched/`` and is still recorded in the manifest, so nothing
downloaded is ever lost.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.download_rubric_assessment import assignment_folder_for
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.manifest import AssignmentEntry
from GAVEL.app.workspace.recording import (
    ArtifactExistsError,
    load_or_create_manifest,
    note_assignment,
    note_course,
    record,
)
from GAVEL.infra.gradescope.http_gradescope_client import http_gradescope_client

STAGING_DIR = "_staging"
UNMATCHED_DIR = "_unmatched"
AUTOGRADER_SUFFIX = "_autograder"

_ILLEGAL = re.compile(r'[\\/:*?"<>|]')
_GRADESCOPE_TAG = re.compile(r"\(\s*gradescope\s*\)", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


def normalise_name(name: str) -> str:
    """Fold a Canvas or Gradescope assignment name for comparison."""
    return _SPACES.sub(" ", _ILLEGAL.sub("", name)).strip().casefold()


def match_gradescope_name(
    name: str, assignments: Sequence[CanvasAssignment]
) -> CanvasAssignment | None:
    """The one Canvas assignment a Gradescope export name refers to, or None.

    Tries an exact match first, then the Canvas name with its
    ``(Gradescope)`` tag removed, then a prefix match either way. Anything
    ambiguous is None rather than a guess.
    """
    key = normalise_name(name)
    if not key:
        return None

    candidates = [(a, normalise_name(a.name)) for a in assignments]
    for rule in (
        lambda canvas: canvas == key,
        lambda canvas: normalise_name(_GRADESCOPE_TAG.sub("", canvas)) == key,
        lambda canvas: canvas.startswith(key) or key.startswith(canvas),
    ):
        hits = [a for a, canvas in candidates if canvas and rule(canvas)]
        if len(hits) == 1:
            return hits[0]
    return None


@dataclass(frozen=True)
class DownloadGradescopeSubmissionsRequest:
    course_id: int
    folder: CourseFolder
    headless: bool = False
    overwrite: bool = False


@dataclass(frozen=True)
class GradescopeArtifact:
    gradescope_name: str
    kind: str  # "submissions" | "autograder"
    saved_path: Path
    assignment_id: int | None  # None when no Canvas assignment matched


@dataclass(frozen=True)
class DownloadGradescopeSubmissionsResult:
    saved_path: Path  # the assignments folder
    artifacts: tuple[GradescopeArtifact, ...]
    message: str

    @property
    def matched(self) -> tuple[GradescopeArtifact, ...]:
        return tuple(a for a in self.artifacts if a.assignment_id is not None)

    @property
    def unmatched(self) -> tuple[GradescopeArtifact, ...]:
        return tuple(a for a in self.artifacts if a.assignment_id is None)


def _env_credentials() -> tuple[str | None, str | None]:
    return os.getenv("CANVAS_USERNAME"), os.getenv("CANVAS_PASSWORD")


class DownloadGradescopeSubmissionsUseCase:
    def __init__(
        self,
        canvas_client: CanvasClient,
        client_factory: Callable[..., Any] = http_gradescope_client,
        credentials: Callable[[], tuple[str | None, str | None]] = _env_credentials,
    ) -> None:
        self._canvas_client = canvas_client
        self._client_factory = client_factory
        self._credentials = credentials

    def execute(
        self, request: DownloadGradescopeSubmissionsRequest
    ) -> DownloadGradescopeSubmissionsResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        username, password = self._credentials()
        if not username or not password:
            raise RuntimeError(
                "Environment variables CANVAS_USERNAME and CANVAS_PASSWORD are required."
            )

        folder = request.folder
        tree = folder.original
        if not request.overwrite:
            self._guard_nothing_downloaded_yet(folder)

        try:
            assignments = list(self._canvas_client.list_assignments(request.course_id))
        except Exception:  # noqa: BLE001 - matching is best effort; unmatched is still kept
            assignments = []

        staging = tree.assignments_dir / STAGING_DIR
        staging.mkdir(parents=True, exist_ok=True)
        client = self._client_factory(
            course_url=f"https://canvas.asu.edu/courses/{request.course_id}",
            headless=request.headless,
            submissions_folder=str(staging),
        )
        client.download_all_assignments(username=username, password=password)

        artifacts: list[GradescopeArtifact] = []
        for zip_path in sorted(staging.glob("*.zip")):
            name = zip_path.stem
            kind = "submissions"
            if name.endswith(AUTOGRADER_SUFFIX):
                name = name[: -len(AUTOGRADER_SUFFIX)]
                kind = "autograder"

            assignment = match_gradescope_name(name, assignments)
            if assignment is None:
                target = tree.assignments_dir / UNMATCHED_DIR / zip_path.name
            else:
                assignment_folder = assignment_folder_for(tree, assignment)
                target = (
                    assignment_folder.submissions_zip
                    if kind == "submissions"
                    else assignment_folder.autograder_zip
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(zip_path), str(target))
            record(
                folder,
                kind,
                target,
                source_id=None if assignment is None else assignment.id,
                label=name,
            )
            if assignment is not None:
                note_assignment(
                    folder,
                    AssignmentEntry(
                        canvas_id=assignment.id,
                        name=assignment.name,
                        module_number=assignment_folder_for(tree, assignment).module_number,
                        has_rubric=assignment.has_rubric,
                        gradescope_name=name,
                    ),
                )
            artifacts.append(
                GradescopeArtifact(
                    gradescope_name=name,
                    kind=kind,
                    saved_path=target,
                    assignment_id=None if assignment is None else assignment.id,
                )
            )

        _remove_if_empty(staging)
        note_course(folder, canvas_course_id=request.course_id)

        result = DownloadGradescopeSubmissionsResult(
            saved_path=tree.assignments_dir,
            artifacts=tuple(artifacts),
            message="",
        )
        message = (
            f"Gradescope submissions for course {request.course_id} saved to "
            f"{tree.assignments_dir} ({len(result.matched)} matched to Canvas assignments"
        )
        if result.unmatched:
            names = ", ".join(sorted({a.gradescope_name for a in result.unmatched}))
            message += f", {len(result.unmatched)} left in {UNMATCHED_DIR}/: {names}"
        message += ")"
        return DownloadGradescopeSubmissionsResult(
            saved_path=result.saved_path, artifacts=result.artifacts, message=message
        )

    @staticmethod
    def _guard_nothing_downloaded_yet(folder: CourseFolder) -> None:
        """Gradescope is all-or-nothing: refuse if any export is already in the folder."""
        manifest = load_or_create_manifest(folder)
        for kind in ("submissions", "autograder"):
            existing = manifest.artifacts_of_kind(kind)
            if existing:
                raise ArtifactExistsError(folder, folder.path / existing[0].path)
        for assignment_folder in folder.original.list_assignments():
            if assignment_folder.submissions_zip.exists():
                raise ArtifactExistsError(folder, assignment_folder.submissions_zip)


def _remove_if_empty(path: Path) -> None:
    try:
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass
