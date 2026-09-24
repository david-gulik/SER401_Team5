from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import load_manifest
from GAVEL.app.workspace.recording import (
    ArtifactExistsError,
    guard_not_downloaded,
    record,
    relative_posix,
    sha256_of,
)

T0 = "2026-09-21T10:00:00+00:00"


@pytest.fixture
def folder(tmp_path: Path) -> CourseFolder:
    return Workspace(tmp_path).course(CourseKey.parse("ser222_25sc_12345"))


def write(path: Path, content: bytes = b"a,b\n1,2\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


class TestHelpers:
    def test_relative_posix(self, folder: CourseFolder) -> None:
        target = folder.original.assignment(7216983, 4).rubric_assessments_json
        assert relative_posix(folder, target) == (
            "original/assignments/7216983_m4/rubric_assessments.json"
        )

    def test_sha256_of(self, tmp_path: Path) -> None:
        path = write(tmp_path / "x.bin", b"hello")
        assert sha256_of(path) == hashlib.sha256(b"hello").hexdigest()


class TestGuard:
    def test_passes_on_fresh_folder(self, folder: CourseFolder) -> None:
        guard_not_downloaded(folder, folder.original.gradebook_csv)

    def test_raises_when_file_exists(self, folder: CourseFolder) -> None:
        target = write(folder.original.gradebook_csv)
        with pytest.raises(ArtifactExistsError) as excinfo:
            guard_not_downloaded(folder, target)
        err = excinfo.value
        assert err.relative_path == "original/gradebook.csv"
        assert err.folder is folder
        assert "SER 222" in str(err)
        assert "ser222_25sc_12345" in str(err)
        assert "delete the course folder" in str(err)
        assert isinstance(err, FileExistsError)

    def test_raises_when_manifest_lists_it_but_file_is_gone(self, folder: CourseFolder) -> None:
        target = write(folder.original.gradebook_csv)
        record(folder, "gradebook", target, now=T0)
        target.unlink()
        with pytest.raises(ArtifactExistsError):
            guard_not_downloaded(folder, target)

    def test_other_artifacts_do_not_block(self, folder: CourseFolder) -> None:
        record(folder, "gradebook", write(folder.original.gradebook_csv), now=T0)
        guard_not_downloaded(folder, folder.original.roster_csv)

    def test_overwrite_skips_both_checks(self, folder: CourseFolder) -> None:
        target = write(folder.original.gradebook_csv)
        record(folder, "gradebook", target, now=T0)
        guard_not_downloaded(folder, target, overwrite=True)


class TestRecord:
    def test_creates_manifest_with_entry(self, folder: CourseFolder) -> None:
        target = write(folder.original.gradebook_csv, b"gradebook")
        entry = record(folder, "gradebook", target, now=T0, gavel_version="0.1.0")

        assert entry.path == "original/gradebook.csv"
        assert entry.kind == "gradebook"
        assert entry.downloaded_at == T0
        assert entry.sha256 == hashlib.sha256(b"gradebook").hexdigest()
        assert entry.size_bytes == len(b"gradebook")
        assert entry.source_id is None

        manifest = load_manifest(folder.manifest_path)
        assert manifest.key == folder.key
        assert manifest.gavel_version == "0.1.0"
        assert manifest.created_at == manifest.updated_at == T0
        assert manifest.artifacts == (entry,)

    def test_second_record_appends_and_keeps_created_at(self, folder: CourseFolder) -> None:
        record(folder, "gradebook", write(folder.original.gradebook_csv), now=T0)
        later = "2026-09-22T10:00:00+00:00"
        record(
            folder,
            "consent_form",
            write(folder.original.consent_form_csv),
            source_id=1234567,
            now=later,
        )
        manifest = load_manifest(folder.manifest_path)
        assert manifest.created_at == T0
        assert manifest.updated_at == later
        assert [a.path for a in manifest.artifacts] == [
            "original/consent_form.csv",
            "original/gradebook.csv",
        ]
        assert manifest.artifact("original/consent_form.csv").source_id == 1234567

    def test_re_record_replaces_checksum(self, folder: CourseFolder) -> None:
        target = write(folder.original.gradebook_csv, b"v1")
        record(folder, "gradebook", target, now=T0)
        write(target, b"v2")
        record(folder, "gradebook", target, now=T0)
        manifest = load_manifest(folder.manifest_path)
        assert len(manifest.artifacts) == 1
        assert manifest.artifacts[0].sha256 == hashlib.sha256(b"v2").hexdigest()

    def test_anonymized_tree_records_under_its_own_prefix(self, folder: CourseFolder) -> None:
        entry = record(folder, "roster", write(folder.anonymized.roster_csv), now=T0)
        assert entry.path == "anonymized/roster.csv"

    def test_rejects_target_outside_folder(self, folder: CourseFolder, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            record(folder, "roster", write(tmp_path / "elsewhere.csv"), now=T0)
