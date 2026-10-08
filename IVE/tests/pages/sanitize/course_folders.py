"""Build course folders on disk for Sanitize tests, with controlled file times."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

# Fixed points in time so "out of date" comparisons do not depend on the clock.
DOWNLOADED = datetime(2026, 9, 20, 9, 0)
ANONYMIZED = datetime(2026, 9, 27, 14, 2)
CHANGED_AFTER = datetime(2026, 10, 1, 8, 30)

_ROSTER_HEADER = (
    "ID,Posting ID,First Name,Last Name,Status,Units,Grade Basis,"
    "Program and Plan,Academic Level,ASURITE,Residency,Zoom Email"
)
_CONSENT_HEADER = (
    "name,id,sis_id,attempt,"
    "Type your name below (leave blank if you do not consent to participate),"
    "Do you consent to participate in this research study?"
)


def set_modified(path: Path, when: datetime) -> None:
    stamp = when.timestamp()
    os.utime(path, (stamp, stamp))


def _write(path: Path, when: datetime, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    set_modified(path, when)


def _consent_form(students: int, consented: int) -> str:
    rows = [_CONSENT_HEADER]
    for n in range(students):
        name = f"Student{n} Example"
        agrees = n < consented
        rows.append(f"{name},{8000 + n},{1000 + n},1,{name if agrees else ''},{agrees}")
    return "\n".join(rows) + "\n"


def _roster(students: int) -> str:
    rows = [_ROSTER_HEADER]
    for n in range(students):
        rows.append(
            f"{1000 + n},{1000 + n}-001,Student{n},Example,Enrolled,3,Standard,"
            f"SER,Senior,student{n},Resident,student{n}@example.com"
        )
    return "\n".join(rows) + "\n"


def build_course(
    workspace_root: Path,
    folder_name: str,
    *,
    consent_form: bool = True,
    roster: bool = True,
    gradebook: bool = True,
    rubric_assessments: int = 0,
    students: int = 4,
    consented: int = 3,
    inputs_at: datetime = DOWNLOADED,
    anonymized_at: datetime | None = None,
    canvas_course_name: str | None = None,
) -> Path:
    """Course folder under ``workspace_root/courses`` holding the files asked for.

    Every student responds to the consent form; the first ``consented`` say yes.
    With ``anonymized_at``, each original file gets an anonymized copy written then.
    """
    course = workspace_root / "courses" / folder_name
    original = course / "original"
    original.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}
    if consent_form:
        files["consent_form.csv"] = _consent_form(students, consented)
    if roster:
        files["roster.csv"] = _roster(students)
    if gradebook:
        files["gradebook.csv"] = "Student,ID\n"
    for index in range(rubric_assessments):
        files[f"assignments/{7216970 + index}_m{index + 1}/rubric_assessments.json"] = "[]\n"

    for relative, text in files.items():
        _write(original / relative, inputs_at, text)
        if anonymized_at is not None:
            _write(course / "anonymized" / relative, anonymized_at, text)

    if canvas_course_name is not None:
        _write_manifest(course, folder_name, canvas_course_name)
    return course


def _write_manifest(course: Path, folder_name: str, canvas_course_name: str) -> None:
    # Only the fields a manifest must carry, taken from the folder name.
    subject_catalog, term_part, class_number = folder_name.split("_")
    subject = "".join(ch for ch in subject_catalog if ch.isalpha()).upper()
    catalog = subject_catalog[len(subject) :]
    manifest = {
        "schema_version": 1,
        "course": {
            "folder": folder_name,
            "subject": subject,
            "catalog_number": catalog,
            "year": 2000 + int(term_part[:2]),
            "term": term_part[2],
            "session": term_part[3:],
            "class_number": class_number,
            "canvas_course_name": canvas_course_name,
        },
        "created_at": "2026-09-20T09:00:00+00:00",
        "updated_at": "2026-09-20T09:00:00+00:00",
    }
    (course / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


# (Canvas name, typed name, consented, latest attempt). typed None means the
# student is on the roster but never submitted the consent form.
StudentRow = tuple[str, str | None, bool | None, int | None]

# One student for every consent outcome, named "First Last" as Canvas shows them.
EVERY_OUTCOME: tuple[StudentRow, ...] = (
    ("Marisol Alvarez", "Marisol Alvarez", True, 2),
    ("Devon Brooks", "Devon", True, 1),
    ("Luca Esposito", "", True, 1),
    ("Hannah Fischer", "Hannah Fischer", False, 1),
    ("Omar Haddad", None, None, None),
    ("Kenji Ishikawa", "Kenij Ishikwa", True, 1),
    ("Chinedu Okafor", "Nedu O.", True, 1),
)


def sis_id(index: int) -> int:
    return 1220440000 + index


def write_students(
    course: Path, students: tuple[StudentRow, ...], when: datetime = DOWNLOADED
) -> None:
    """Replace a course's consent form and roster with exactly these students."""
    consent = [_CONSENT_HEADER]
    roster = [_ROSTER_HEADER]
    for n, (name, typed, consented, attempt) in enumerate(students):
        first, last = name.split(" ", 1)
        roster.append(
            f"{sis_id(n)},{sis_id(n)}-001,{first},{last},Enrolled,3,Standard,SER,Senior,"
            f"s{n},Resident,s{n}@example.com"
        )
        if typed is None:
            continue
        for a in range(1, (attempt or 1) + 1):
            consent.append(f"{name},{9000 + n},{sis_id(n)},{a},{typed},{consented}")
    _write(course / "original" / "consent_form.csv", when, "\n".join(consent) + "\n")
    _write(course / "original" / "roster.csv", when, "\n".join(roster) + "\n")
