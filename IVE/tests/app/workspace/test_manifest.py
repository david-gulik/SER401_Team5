from __future__ import annotations

import json
from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasModule
from GAVEL.app.workspace.layout import CourseKey
from GAVEL.app.workspace.manifest import (
    MANIFEST_SCHEMA_VERSION,
    ArtifactEntry,
    AssignmentEntry,
    ManifestError,
    load_manifest,
    manifest_from_dict,
    manifest_to_dict,
    new_manifest,
    record_artifact,
    record_assignment,
    save_manifest,
    set_course_metadata,
)

KEY = CourseKey.parse("ser222_25sc_12345")
T0 = "2026-09-21T10:00:00+00:00"
T1 = "2026-09-21T10:05:00+00:00"
SHA = "0" * 64


def artifact(path: str = "original/gradebook.csv", **overrides: object) -> ArtifactEntry:
    fields: dict[str, object] = {
        "kind": "gradebook",
        "path": path,
        "downloaded_at": T0,
        "sha256": SHA,
        "size_bytes": 10,
    }
    fields.update(overrides)
    return ArtifactEntry(**fields)  # type: ignore[arg-type]


class TestArtifactEntry:
    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            artifact(kind="spreadsheet")

    @pytest.mark.parametrize("path", ["", "/abs/roster.csv", "original\\roster.csv", "C:/x.csv"])
    def test_non_relative_paths_rejected(self, path: str) -> None:
        with pytest.raises(ValueError, match="relative"):
            artifact(path=path)


class TestNewManifest:
    def test_defaults(self) -> None:
        m = new_manifest(KEY, now=T0)
        assert m.schema_version == MANIFEST_SCHEMA_VERSION
        assert m.key == KEY
        assert m.created_at == m.updated_at == T0
        assert m.artifacts == () and m.assignments == () and m.modules == ()

    def test_course_fields(self) -> None:
        m = new_manifest(KEY, term_code="2251", canvas_course_id=253450, gavel_version="0.1.0")
        assert m.term_code == "2251"
        assert m.canvas_course_id == 253450
        assert m.gavel_version == "0.1.0"


class TestRecording:
    def test_record_artifact_adds_and_stamps(self) -> None:
        m = record_artifact(new_manifest(KEY, now=T0), artifact(), now=T1)
        assert m.artifacts == (artifact(),)
        assert m.updated_at == T1
        assert m.created_at == T0

    def test_record_artifact_replaces_same_path(self) -> None:
        m = record_artifact(new_manifest(KEY, now=T0), artifact(sha256="a" * 64))
        m = record_artifact(m, artifact(sha256="b" * 64))
        assert len(m.artifacts) == 1
        assert m.artifacts[0].sha256 == "b" * 64

    def test_artifacts_kept_sorted_by_path(self) -> None:
        m = new_manifest(KEY, now=T0)
        m = record_artifact(m, artifact("original/roster.csv", kind="roster"))
        m = record_artifact(m, artifact("original/gradebook.csv"))
        assert [a.path for a in m.artifacts] == ["original/gradebook.csv", "original/roster.csv"]

    def test_lookup_helpers(self) -> None:
        m = record_artifact(new_manifest(KEY, now=T0), artifact())
        assert m.artifact("original/gradebook.csv") == artifact()
        assert m.artifact("original/roster.csv") is None
        assert m.artifacts_of_kind("gradebook") == (artifact(),)
        assert m.artifacts_of_kind("roster") == ()

    def test_record_assignment_replaces_same_id(self) -> None:
        m = new_manifest(KEY, now=T0)
        m = record_assignment(m, AssignmentEntry(7216983, "Module 4: ADJ", 4, True))
        m = record_assignment(m, AssignmentEntry(7216974, "Module 3: Activity", 3, False))
        m = record_assignment(m, AssignmentEntry(7216983, "Module 4: ADJ Problem Set", 4, True))
        assert [a.canvas_id for a in m.assignments] == [7216974, 7216983]
        assert m.assignment(7216983).name == "Module 4: ADJ Problem Set"
        assert m.assignment(1) is None

    def test_set_course_metadata_leaves_none_alone(self) -> None:
        m = new_manifest(KEY, canvas_course_id=1, now=T0)
        m = set_course_metadata(
            m, canvas_course_name="SER 222", modules=(CanvasModule(5, "Module 1"),), now=T1
        )
        assert m.canvas_course_id == 1
        assert m.canvas_course_name == "SER 222"
        assert m.modules == (CanvasModule(5, "Module 1"),)
        assert m.updated_at == T1


def full_manifest():
    m = new_manifest(
        KEY,
        term_code="2251",
        canvas_course_id=253450,
        canvas_course_name="SER 222 Spring 2025 C",
        canvas_course_code="2025SpringC-X-SER222-12345",
        gavel_version="0.1.0",
        now=T0,
    )
    m = set_course_metadata(m, modules=(CanvasModule(1, "Module 1"), CanvasModule(2, "Module 2")))
    m = record_assignment(
        m,
        AssignmentEntry(7216983, "Mod 4: ADJ Problem Set", 4, True, points_possible=30.0),
    )
    m = record_artifact(m, artifact("original/roster.csv", kind="roster"))
    m = record_artifact(
        m,
        artifact(
            "original/assignments/7216983_m4/rubric_assessments.json",
            kind="rubric_assessments",
            source_id=7216983,
        ),
        now=T1,
    )
    return m


class TestSerialisation:
    def test_dict_round_trip(self) -> None:
        m = full_manifest()
        assert manifest_from_dict(manifest_to_dict(m)) == m

    def test_dict_shape(self) -> None:
        d = manifest_to_dict(full_manifest())
        assert d["schema_version"] == 1
        assert d["course"]["folder"] == "ser222_25sc_12345"
        assert d["course"]["subject"] == "SER"
        assert d["course"]["canvas_course_id"] == 253450
        assert d["modules"][0] == {"id": 1, "name": "Module 1"}
        assert d["assignments"][0]["canvas_id"] == 7216983
        assert (
            d["artifacts"][0]["path"] == "original/assignments/7216983_m4/rubric_assessments.json"
        )
        assert d["artifacts"][0]["source_id"] == 7216983

    def test_dict_matches_schema_keys(self) -> None:
        """Every key we write is declared in docs/manifest.schema.json, and vice versa."""
        schema = json.loads(
            (Path(__file__).parents[3] / "docs" / "manifest.schema.json").read_text(
                encoding="utf-8"
            )
        )
        d = manifest_to_dict(full_manifest())
        assert set(d) == set(schema["properties"])
        assert set(d["course"]) == set(schema["properties"]["course"]["properties"])
        assert set(d["assignments"][0]) == set(
            schema["properties"]["assignments"]["items"]["properties"]
        )
        assert set(d["artifacts"][0]) == set(
            schema["properties"]["artifacts"]["items"]["properties"]
        )
        assert set(d["modules"][0]) == set(schema["properties"]["modules"]["items"]["properties"])

    def test_save_and_load(self, tmp_path: Path) -> None:
        path = tmp_path / "courses" / "ser222_25sc_12345" / "manifest.json"
        save_manifest(path, full_manifest())
        assert path.exists()
        assert not path.with_name("manifest.json.tmp").exists()
        assert load_manifest(path) == full_manifest()

    def test_saved_json_is_pretty_and_stable(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        save_manifest(path, full_manifest())
        first = path.read_text(encoding="utf-8")
        save_manifest(path, full_manifest())
        assert path.read_text(encoding="utf-8") == first
        assert first.startswith("{\n  ")

    def test_unsupported_schema_version(self) -> None:
        d = manifest_to_dict(full_manifest())
        d["schema_version"] = 2
        with pytest.raises(ManifestError, match="schema_version 2"):
            manifest_from_dict(d)

    def test_missing_course_block(self) -> None:
        d = manifest_to_dict(full_manifest())
        del d["course"]
        with pytest.raises(ManifestError, match="malformed"):
            manifest_from_dict(d)

    def test_invalid_json_file(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ManifestError, match="not valid JSON"):
            load_manifest(path)

    def test_non_object_file(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(ManifestError, match="JSON object"):
            load_manifest(path)
