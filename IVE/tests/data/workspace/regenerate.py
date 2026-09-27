"""Rebuild the fixture course folder next to this file with the real workspace code.

Run from ``IVE/``::

    python tests/data/workspace/regenerate.py

Every file is written with LF line endings and the manifest checksums are
computed from those bytes. ``.gitattributes`` pins this folder to LF on every
platform, so the checksums match on Windows and Linux alike. Regenerate after
changing the layout, the manifest shape, or the rubric JSON codec.
"""

from __future__ import annotations

import sys
from pathlib import Path

IVE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(IVE_ROOT))

from GAVEL.app.dtos.canvas_course import CanvasModule  # noqa: E402
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace  # noqa: E402
from GAVEL.app.workspace.manifest import (  # noqa: E402
    AssignmentEntry,
    load_manifest,
    record_assignment,
    save_manifest,
    set_course_metadata,
)
from GAVEL.app.workspace.recording import record  # noqa: E402
from GAVEL.infra.json.rubric_json import assessments_to_json, definition_to_json  # noqa: E402
from tests.app.usecases.test_download_rubric_assessment import (  # noqa: E402
    RUBRIC_ASSESSMENTS,
    RUBRIC_DEFINITION,
)

DATA_DIR = IVE_ROOT / "tests" / "data"
ROOT = DATA_DIR / "workspace"
FOLDER_NAME = "ser222_25sc_12345"
STAMP = "2026-09-21T10:00:00+00:00"


def write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def copy_lf(source: Path, target: Path) -> None:
    write_lf(target, source.read_text(encoding="utf-8"))


def build(folder: CourseFolder) -> None:
    original = folder.original
    copy_lf(DATA_DIR / "test_roster.csv", original.roster_csv)
    copy_lf(DATA_DIR / "test_gradebook.csv", original.gradebook_csv)
    copy_lf(DATA_DIR / "test_consentform.csv", original.consent_form_csv)
    record(folder, "roster", original.roster_csv, now=STAMP, gavel_version="0.1.0")
    record(folder, "gradebook", original.gradebook_csv, now=STAMP)
    record(folder, "consent_form", original.consent_form_csv, source_id=1234567, now=STAMP)

    with_rubric = original.assignment(7216983, 4)
    write_lf(with_rubric.rubric_definition_json, definition_to_json(RUBRIC_DEFINITION) + "\n")
    write_lf(with_rubric.rubric_assessments_json, assessments_to_json(RUBRIC_ASSESSMENTS) + "\n")
    record(
        folder,
        "rubric_definition",
        with_rubric.rubric_definition_json,
        source_id=7216983,
        now=STAMP,
    )
    record(
        folder,
        "rubric_assessments",
        with_rubric.rubric_assessments_json,
        source_id=7216983,
        now=STAMP,
    )

    # An assignment with no rubric attached: folder exists, no definition file.
    without_rubric = original.assignment(7216972, 3)
    write_lf(without_rubric.rubric_assessments_json, "[]\n")
    record(
        folder,
        "rubric_assessments",
        without_rubric.rubric_assessments_json,
        source_id=7216972,
        now=STAMP,
    )

    header = (DATA_DIR / "test_roster.csv").read_text(encoding="utf-8").splitlines()[0]
    rows = [header] + [
        f'"{n}","","Anon","Anon{n}","ENRL","3","Standard","","Senior","aanon{n}","Resident","aanon{n}@asu.edu"'
        for n in (1, 2)
    ]
    write_lf(folder.anonymized.roster_csv, "\n".join(rows) + "\n")
    record(folder, "roster", folder.anonymized.roster_csv, now=STAMP)

    manifest = load_manifest(folder.manifest_path)
    manifest = set_course_metadata(
        manifest,
        canvas_course_id=253450,
        canvas_course_name="SER 222 Spring 2025 C",
        canvas_course_code="2025SpringC-X-SER222-12345",
        term_code="2251",
        modules=(CanvasModule(101, "Module 3: Lists"), CanvasModule(102, "Module 4: Analysis")),
        now=STAMP,
    )
    manifest = record_assignment(
        manifest,
        AssignmentEntry(
            7216972, "Module 3: Programming (Gradescope)", 3, False, points_possible=26.0
        ),
        now=STAMP,
    )
    manifest = record_assignment(
        manifest,
        AssignmentEntry(7216983, "Module 4: ADJ Problem Set", 4, True, points_possible=30.0),
        now=STAMP,
    )
    save_manifest(folder.manifest_path, manifest)
    # save_manifest uses the platform newline; the manifest is not checksummed but keep it LF too.
    write_lf(folder.manifest_path, folder.manifest_path.read_text(encoding="utf-8"))


def main() -> None:
    folder = Workspace(ROOT).course(CourseKey.parse(FOLDER_NAME))
    # Delete files only: OneDrive and antivirus can hold a directory lock on
    # Windows that makes rmtree fail, and build() rewrites every file anyway.
    for path in folder.path.rglob("*"):
        if path.is_file():
            path.unlink()
    build(folder)
    for path in sorted(folder.path.rglob("*")):
        if path.is_file():
            print(path.relative_to(ROOT).as_posix(), path.stat().st_size)


if __name__ == "__main__":
    main()
