"""Roster-versus-Canvas class check for the download page.

ASU's SIS creates Canvas courses with a code like ``2026FallC-X-SER402-87275``:
term, campus, subject and catalog number, then the five-digit class number of
every section in the course (a cross-listed course carries several). The
myASU roster is keyed by that same class number, so the two selections can be
checked against each other, and the course for a roster class found, without
another API call.

Kept free of PyQt imports so the rules stay unit-testable without a GUI.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection
from GAVEL.app.workspace.layout import TERM_DIGIT_LETTERS, CourseKey

_CLASS_NUMBER = re.compile(r"\d{5}")
_TERM_CODE = re.compile(r"2\d\d[1479]")


def class_numbers_in_course_code(course_code: str | None) -> tuple[str, ...]:
    """Five-digit class numbers embedded in a Canvas course code, in order.

    Empty when the code carries none: training courses (``TRN-...``), courses
    an instructor renamed, or courses with no code at all.
    """
    if not course_code:
        return ()
    return tuple(p for p in course_code.split("-") if _CLASS_NUMBER.fullmatch(p))


def _in_term(course: CanvasCourse, term_code: str) -> bool:
    """Whether the course code's term is the myASU term ``2267`` (Fall 2026)."""
    key = CourseKey.from_canvas_course_code(course.course_code)
    if key is None:
        return False
    return key.year == 2000 + int(term_code[1:3]) and key.term == TERM_DIGIT_LETTERS[term_code[3]]


def course_for_class(
    class_number: str, term_code: str, courses: Sequence[CanvasCourse]
) -> CanvasCourse | None:
    """The one Canvas course whose code carries the roster class, or None.

    Class numbers repeat across terms, so a valid term code narrows the
    candidates to that term. None when nothing matches or more than one
    course still does; the caller then leaves the Canvas selection alone.
    """
    if not class_number:
        return None
    matches = [c for c in courses if class_number in class_numbers_in_course_code(c.course_code)]
    term_code = term_code.strip()
    if _TERM_CODE.fullmatch(term_code):
        matches = [c for c in matches if _in_term(c, term_code)]
    return matches[0] if len(matches) == 1 else None


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
