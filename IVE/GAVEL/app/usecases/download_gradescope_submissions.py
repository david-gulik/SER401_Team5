"""Gradescope bulk exports into ``original/submissions/m<module>/``.

The Gradescope scraper only knows Gradescope's assignment names and writes
``<name>.zip`` and ``<name>_autograder.zip`` into one folder. This use case
lets it write into a staging folder, then files each export by module: the
assignment Gradescope grades and the one that carries the human rubric are
usually different Canvas assignments in the same module, so the module is
what ties submissions to rubric assessments. Submissions are extracted next
to the zip; autograder zips go to the workspace-level ``autograders/`` area.
Anything whose module cannot be told goes to ``submissions/_unmatched/`` and
is still recorded in the manifest, so nothing downloaded is ever lost.
"""

from __future__ import annotations

import os
import re
import shutil
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.workspace.layout import CourseFolder, Workspace, module_number_from_name
from GAVEL.app.workspace.manifest import AssignmentEntry
from GAVEL.app.workspace.recording import (
    ArtifactExistsError,
    artifact_path,
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
_MODULE_PREFIX = re.compile(r"^\s*mod(?:ule)?\s*\d+\s*[:\-]?\s*", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


def normalise_name(name: str) -> str:
    """Fold a Canvas or Gradescope assignment name for comparison."""
    return _SPACES.sub(" ", _ILLEGAL.sub("", name)).strip().casefold()


def match_gradescope_name(
    name: str, assignments: Sequence[CanvasAssignment]
) -> CanvasAssignment | None:
    """The one Canvas assignment a Gradescope export name refers to, or None.

    Tries an exact match first, then the Canvas name with its
    ``(Gradescope)`` tag removed, then the Canvas name without its leading
    ``Module N:`` (Gradescope assignments are often named without it), then a
    prefix match either way. Anything ambiguous is None rather than a guess.
    """
    key = normalise_name(name)
    if not key:
        return None

    candidates = [(a, normalise_name(a.name)) for a in assignments]
    for rule in (
        lambda canvas: canvas == key,
        lambda canvas: normalise_name(_GRADESCOPE_TAG.sub("", canvas)) == key,
        lambda canvas: (
            normalise_name(_MODULE_PREFIX.sub("", _GRADESCOPE_TAG.sub("", canvas))) == key
        ),
        lambda canvas: canvas.startswith(key) or key.startswith(canvas),
    ):
        hits = [a for a, canvas in candidates if canvas and rule(canvas)]
        if len(hits) == 1:
            return hits[0]
    return None


def module_for_export(
    name: str, assignments: Sequence[CanvasAssignment]
) -> tuple[int | None, CanvasAssignment | None]:
    """Which module a Gradescope export belongs to, and the Canvas assignment it names.

    The module number in the Gradescope assignment name wins; otherwise the
    matching Canvas assignment's name is read for one.
    """
    assignment = match_gradescope_name(name, assignments)
    module = module_number_from_name(name)
    if module is None and assignment is not None:
        module = module_number_from_name(assignment.name)
    return module, assignment


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
    module_number: int | None  # None when the module could not be told
    assignment_id: int | None = None  # the Canvas assignment with the same name, when one matched


@dataclass(frozen=True)
class DownloadGradescopeSubmissionsResult:
    saved_path: Path  # the submissions folder
    artifacts: tuple[GradescopeArtifact, ...]
    message: str

    @property
    def matched(self) -> tuple[GradescopeArtifact, ...]:
        return tuple(a for a in self.artifacts if a.module_number is not None)

    @property
    def unmatched(self) -> tuple[GradescopeArtifact, ...]:
        return tuple(a for a in self.artifacts if a.module_number is None)


def _env_credentials() -> tuple[str | None, str | None]:
    return os.getenv("CANVAS_USERNAME"), os.getenv("CANVAS_PASSWORD")


class DownloadGradescopeSubmissionsUseCase:
    def __init__(
        self,
        canvas_client: CanvasClient,
        client_factory: Callable[..., Any] = http_gradescope_client,
        credentials: Callable[[], tuple[str | None, str | None]] = _env_credentials,
        browser: Any = None,
    ) -> None:
        """``browser`` is the app's shared login browser; without it the scraper opens its own."""
        self._canvas_client = canvas_client
        self._client_factory = client_factory
        self._credentials = credentials
        self._browser = browser

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
        workspace = Workspace(folder.workspace_root)
        if not request.overwrite:
            self._guard_nothing_downloaded_yet(folder)

        assignments_unavailable = False
        try:
            assignments = list(self._canvas_client.list_assignments(request.course_id))
        except Exception:  # noqa: BLE001 - matching is best effort; unmatched is still kept
            assignments = []
            assignments_unavailable = True

        staging = tree.submissions_dir / STAGING_DIR
        staging.mkdir(parents=True, exist_ok=True)
        client_options: dict[str, Any] = {
            "course_url": f"https://canvas.asu.edu/courses/{request.course_id}",
            "headless": request.headless,
            "submissions_folder": str(staging),
        }
        if self._browser is not None:
            client_options["browser"] = self._browser
        client = self._client_factory(**client_options)
        client.download_all_assignments(username=username, password=password)

        artifacts: list[GradescopeArtifact] = []
        for zip_path in sorted(staging.glob("*.zip")):
            name = zip_path.stem
            kind = "submissions"
            if name.endswith(AUTOGRADER_SUFFIX):
                name = name[: -len(AUTOGRADER_SUFFIX)]
                kind = "autograder"

            module, assignment = module_for_export(name, assignments)
            if module is None:
                target = tree.submissions_dir / UNMATCHED_DIR / zip_path.name
            elif kind == "autograder":
                target = workspace.autograder_snapshot(folder.key, module)
            else:
                target = tree.module_submissions(module).zip_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(zip_path), str(target))
            if module is not None and kind == "submissions":
                _extract(target, tree.module_submissions(module).extracted_dir)

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
                        module_number=module,
                        has_rubric=assignment.has_rubric,
                        gradescope_name=name,
                    ),
                )
            artifacts.append(
                GradescopeArtifact(
                    gradescope_name=name,
                    kind=kind,
                    saved_path=target,
                    module_number=module,
                    assignment_id=None if assignment is None else assignment.id,
                )
            )

        _remove_if_empty(staging)
        note_course(folder, canvas_course_id=request.course_id)

        result = DownloadGradescopeSubmissionsResult(
            saved_path=tree.submissions_dir, artifacts=tuple(artifacts), message=""
        )
        modules = sorted({a.module_number for a in result.matched if a.module_number is not None})
        message = (
            f"Gradescope exports for course {request.course_id} saved to {tree.submissions_dir} "
            f"({len(result.matched)} filed under module(s) "
            f"{', '.join(f'm{m}' for m in modules) or 'none'}"
        )
        if result.unmatched:
            names = ", ".join(sorted({a.gradescope_name for a in result.unmatched}))
            message += f", {len(result.unmatched)} left in {UNMATCHED_DIR}/: {names}"
        if assignments_unavailable:
            message += "; the Canvas assignment list could not be fetched"
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
                raise ArtifactExistsError(folder, artifact_path(folder, existing[0]))
        for module in folder.original.list_module_submissions():
            if module.zip_path.exists():
                raise ArtifactExistsError(folder, module.zip_path)


def _extract(zip_path: Path, destination: Path) -> None:
    """Unzip an export next to itself so the files are ready for an autograder run."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)


def _remove_if_empty(path: Path) -> None:
    try:
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass
