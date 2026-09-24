"""``manifest.json``: what has been downloaded into a course folder, and when.

The manifest is written by GAVEL. Every download records the
file it produced (relative path, timestamp, checksum) and every rubric
download records the assignment it belongs to. Downstream tooling loads this
one file instead of guessing from filenames.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from GAVEL.app.dtos.canvas_course import CanvasModule
from GAVEL.app.workspace.layout import CourseKey

MANIFEST_SCHEMA_VERSION = 1

ARTIFACT_KINDS = frozenset(
    {
        "roster",
        "gradebook",
        "consent_form",
        "quiz",
        "rubric_definition",
        "rubric_assessments",
        "submissions",
        "autograder",
    }
)


class ManifestError(ValueError):
    """A manifest file that cannot be understood."""


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ArtifactEntry:
    """One downloaded file."""

    kind: str
    path: str
    downloaded_at: str
    sha256: str
    size_bytes: int
    source_id: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in ARTIFACT_KINDS:
            raise ValueError(
                f"unknown artifact kind {self.kind!r}; expected one of {sorted(ARTIFACT_KINDS)}"
            )
        if not self.path or self.path.startswith("/") or "\\" in self.path or ":" in self.path:
            raise ValueError(
                f"artifact path must be relative with '/' separators, got {self.path!r}"
            )


@dataclass(frozen=True)
class AssignmentEntry:
    """A Canvas assignment as known at download time.

    ``due_at`` and ``points_possible`` stay None until the Canvas client
    exposes them; the fields exist now so the manifest shape does not change
    when they arrive.
    """

    canvas_id: int
    name: str
    module_number: int | None
    has_rubric: bool
    due_at: str | None = None
    points_possible: float | None = None
    gradescope_name: str | None = None


@dataclass(frozen=True)
class CourseManifest:
    schema_version: int
    key: CourseKey
    created_at: str
    updated_at: str
    term_code: str | None = None
    canvas_course_id: int | None = None
    canvas_course_name: str | None = None
    canvas_course_code: str | None = None
    gavel_version: str | None = None
    modules: tuple[CanvasModule, ...] = ()
    assignments: tuple[AssignmentEntry, ...] = ()
    artifacts: tuple[ArtifactEntry, ...] = ()

    def artifact(self, path: str) -> ArtifactEntry | None:
        return next((a for a in self.artifacts if a.path == path), None)

    def artifacts_of_kind(self, kind: str) -> tuple[ArtifactEntry, ...]:
        return tuple(a for a in self.artifacts if a.kind == kind)

    def assignment(self, canvas_id: int) -> AssignmentEntry | None:
        return next((a for a in self.assignments if a.canvas_id == canvas_id), None)


def new_manifest(
    key: CourseKey,
    *,
    term_code: str | None = None,
    canvas_course_id: int | None = None,
    canvas_course_name: str | None = None,
    canvas_course_code: str | None = None,
    gavel_version: str | None = None,
    now: str | None = None,
) -> CourseManifest:
    stamp = now or utc_now_iso()
    return CourseManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        key=key,
        created_at=stamp,
        updated_at=stamp,
        term_code=term_code,
        canvas_course_id=canvas_course_id,
        canvas_course_name=canvas_course_name,
        canvas_course_code=canvas_course_code,
        gavel_version=gavel_version,
    )


def record_artifact(
    manifest: CourseManifest, entry: ArtifactEntry, *, now: str | None = None
) -> CourseManifest:
    """Manifest with ``entry`` added, replacing any entry at the same path."""
    kept = tuple(a for a in manifest.artifacts if a.path != entry.path)
    return replace(
        manifest,
        artifacts=tuple(sorted((*kept, entry), key=lambda a: a.path)),
        updated_at=now or utc_now_iso(),
    )


def record_assignment(
    manifest: CourseManifest, entry: AssignmentEntry, *, now: str | None = None
) -> CourseManifest:
    """Manifest with ``entry`` added, replacing any entry with the same Canvas id."""
    kept = tuple(a for a in manifest.assignments if a.canvas_id != entry.canvas_id)
    return replace(
        manifest,
        assignments=tuple(sorted((*kept, entry), key=lambda a: a.canvas_id)),
        updated_at=now or utc_now_iso(),
    )


def set_course_metadata(
    manifest: CourseManifest,
    *,
    canvas_course_id: int | None = None,
    canvas_course_name: str | None = None,
    canvas_course_code: str | None = None,
    term_code: str | None = None,
    modules: tuple[CanvasModule, ...] | None = None,
    now: str | None = None,
) -> CourseManifest:
    """Manifest with the given course fields filled in; None arguments leave a field alone."""
    changes: dict[str, Any] = {"updated_at": now or utc_now_iso()}
    if canvas_course_id is not None:
        changes["canvas_course_id"] = canvas_course_id
    if canvas_course_name is not None:
        changes["canvas_course_name"] = canvas_course_name
    if canvas_course_code is not None:
        changes["canvas_course_code"] = canvas_course_code
    if term_code is not None:
        changes["term_code"] = term_code
    if modules is not None:
        changes["modules"] = tuple(modules)
    return replace(manifest, **changes)



def manifest_to_dict(manifest: CourseManifest) -> dict[str, Any]:
    key = manifest.key
    return {
        "schema_version": manifest.schema_version,
        "course": {
            "folder": key.folder_name,
            "subject": key.subject,
            "catalog_number": key.catalog_number,
            "year": key.year,
            "term": key.term,
            "session": key.session,
            "class_number": key.class_number,
            "term_code": manifest.term_code,
            "canvas_course_id": manifest.canvas_course_id,
            "canvas_course_name": manifest.canvas_course_name,
            "canvas_course_code": manifest.canvas_course_code,
        },
        "created_at": manifest.created_at,
        "updated_at": manifest.updated_at,
        "gavel_version": manifest.gavel_version,
        "modules": [{"id": m.id, "name": m.name} for m in manifest.modules],
        "assignments": [
            {
                "canvas_id": a.canvas_id,
                "name": a.name,
                "module_number": a.module_number,
                "has_rubric": a.has_rubric,
                "due_at": a.due_at,
                "points_possible": a.points_possible,
                "gradescope_name": a.gradescope_name,
            }
            for a in sorted(manifest.assignments, key=lambda a: a.canvas_id)
        ],
        "artifacts": [
            {
                "kind": a.kind,
                "path": a.path,
                "downloaded_at": a.downloaded_at,
                "sha256": a.sha256,
                "size_bytes": a.size_bytes,
                "source_id": a.source_id,
            }
            for a in sorted(manifest.artifacts, key=lambda a: a.path)
        ],
    }


def manifest_from_dict(data: dict[str, Any]) -> CourseManifest:
    try:
        version = int(data["schema_version"])
        if version != MANIFEST_SCHEMA_VERSION:
            raise ManifestError(
                f"manifest schema_version {version} is not supported "
                f"(this GAVEL writes version {MANIFEST_SCHEMA_VERSION})"
            )
        course = data["course"]
        key = CourseKey(
            subject=course["subject"],
            catalog_number=course["catalog_number"],
            year=int(course["year"]),
            term=course["term"],
            session=course.get("session") or "",
            class_number=course["class_number"],
        )
        return CourseManifest(
            schema_version=version,
            key=key,
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            term_code=course.get("term_code"),
            canvas_course_id=course.get("canvas_course_id"),
            canvas_course_name=course.get("canvas_course_name"),
            canvas_course_code=course.get("canvas_course_code"),
            gavel_version=data.get("gavel_version"),
            modules=tuple(
                CanvasModule(id=int(m["id"]), name=str(m["name"])) for m in data.get("modules", [])
            ),
            assignments=tuple(
                AssignmentEntry(
                    canvas_id=int(a["canvas_id"]),
                    name=str(a["name"]),
                    module_number=a.get("module_number"),
                    has_rubric=bool(a["has_rubric"]),
                    due_at=a.get("due_at"),
                    points_possible=a.get("points_possible"),
                    gradescope_name=a.get("gradescope_name"),
                )
                for a in data.get("assignments", [])
            ),
            artifacts=tuple(
                ArtifactEntry(
                    kind=str(a["kind"]),
                    path=str(a["path"]),
                    downloaded_at=str(a["downloaded_at"]),
                    sha256=str(a["sha256"]),
                    size_bytes=int(a["size_bytes"]),
                    source_id=a.get("source_id"),
                )
                for a in data.get("artifacts", [])
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ManifestError):
            raise
        raise ManifestError(f"malformed manifest: {exc}") from exc


def load_manifest(path: Path) -> CourseManifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"{path} does not contain a JSON object")
    return manifest_from_dict(data)


def save_manifest(path: Path, manifest: CourseManifest) -> None:
    """Write atomically: a half-written manifest is worse than a stale one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(manifest_to_dict(manifest), indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
