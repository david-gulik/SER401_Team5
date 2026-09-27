"""What a download use case does before and after writing a file.

Two calls, in this order:

    target = folder.original.gradebook_csv
    guard_not_downloaded(folder, target)        # raises ArtifactExistsError
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(...)
    record(folder, "gradebook", target)         # hashes, stamps, saves manifest

Keeping both here means the re-download policy agreed with Dr. Acuna (warn,
never overwrite, delete the folder to refresh) lives in one place.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.manifest import (
    ArtifactEntry,
    CourseManifest,
    load_manifest,
    new_manifest,
    record_artifact,
    save_manifest,
    utc_now_iso,
)


class ArtifactExistsError(FileExistsError):
    """The file was already downloaded for this course."""

    def __init__(self, folder: CourseFolder, target: Path) -> None:
        self.folder = folder
        self.target = target
        self.relative_path = relative_posix(folder, target)
        super().__init__(
            f"{self.relative_path} was already downloaded for {folder.key.course_label} "
            f"({folder.key.folder_name}). To refresh it, delete the course folder "
            f"{folder.path} and download again."
        )


def relative_posix(folder: CourseFolder, target: Path) -> str:
    """``target`` relative to the course folder, with ``/`` separators."""
    return target.relative_to(folder.path).as_posix()


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def guard_not_downloaded(folder: CourseFolder, target: Path, overwrite: bool = False) -> None:
    """Raise ``ArtifactExistsError`` if ``target`` exists on disk or in the manifest."""
    if overwrite:
        return
    if target.exists():
        raise ArtifactExistsError(folder, target)
    if folder.manifest_path.exists():
        manifest = load_manifest(folder.manifest_path)
        if manifest.artifact(relative_posix(folder, target)) is not None:
            raise ArtifactExistsError(folder, target)


def load_or_create_manifest(
    folder: CourseFolder, *, gavel_version: str | None = None, now: str | None = None
) -> CourseManifest:
    if folder.manifest_path.exists():
        return load_manifest(folder.manifest_path)
    return new_manifest(folder.key, gavel_version=gavel_version, now=now)


def record(
    folder: CourseFolder,
    kind: str,
    target: Path,
    *,
    source_id: int | None = None,
    gavel_version: str | None = None,
    now: str | None = None,
) -> ArtifactEntry:
    """Add ``target`` to the course manifest and save it. Returns the entry written."""
    stamp = now or utc_now_iso()
    entry = ArtifactEntry(
        kind=kind,
        path=relative_posix(folder, target),
        downloaded_at=stamp,
        sha256=sha256_of(target),
        size_bytes=target.stat().st_size,
        source_id=source_id,
    )
    manifest = load_or_create_manifest(folder, gavel_version=gavel_version, now=stamp)
    manifest = record_artifact(manifest, entry, now=stamp)
    save_manifest(folder.manifest_path, manifest)
    return entry
