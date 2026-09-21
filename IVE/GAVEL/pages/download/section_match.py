"""Roster-versus-Canvas class check for the download page.

ASU's SIS creates Canvas courses with a code like ``2026FallC-X-SER402-87275``:
term, campus, subject and catalog number, then the five-digit class number of
every section in the course (a cross-listed course carries several). The
myASU roster is keyed by that same class number, so the two selections can be
checked against each other without another API call.

Kept free of PyQt imports so the rules stay unit-testable without a GUI.
"""

from __future__ import annotations

import re

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection

_CLASS_NUMBER = re.compile(r"\d{5}")


def class_numbers_in_course_code(course_code: str | None) -> tuple[str, ...]:
    """Five-digit class numbers embedded in a Canvas course code, in order.

    Empty when the code carries none: training courses (``TRN-...``), courses
    an instructor renamed, or courses with no code at all.
    """
    if not course_code:
        return ()
    return tuple(p for p in course_code.split("-") if _CLASS_NUMBER.fullmatch(p))


def section_mismatch(
    class_number: str,
    course: CanvasCourse | None,
    section: ClassSection | None = None,
) -> str | None:
    """Warning text when the roster class is not part of the Canvas course.

    None whenever there is nothing to compare: no class number, no course, or
    a course code that carries no class numbers. ``section`` only enriches the
    message when the roster side came from a catalog search.
    """
    if not class_number or course is None:
        return None
    numbers = class_numbers_in_course_code(course.course_code)
    if not numbers or class_number in numbers:
        return None

    roster_label = f"class {class_number}"
    if section is not None:
        roster_label = f"{section.subject} {section.catalog_number} {roster_label}"
    noun = "class" if len(numbers) == 1 else "classes"
    course_label = f"{course.course_code} ({noun} {', '.join(numbers)})"
    return (
        f"The myASU roster is for {roster_label}, but the selected Canvas course is "
        f"{course_label}. Downloads will still run, but the roster and Canvas data "
        "may not be what you are looking for. Verify you have the right courses selected."
    )
