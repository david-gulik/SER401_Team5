"""Which course folder the download page's selections point at.

The GUI collects a Canvas course, a roster class number, a term and maybe a
catalog search result. This turns those into one ``CourseKey`` or one
sentence explaining why it cannot, so the view model, the folder preview and
the CLI all agree. Pure: no Qt, no I/O.
"""

from __future__ import annotations

import re

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection
from GAVEL.app.workspace.layout import TERM_DIGIT_LETTERS, CourseKey

NOTHING_TO_NAME_FROM = (
    "Select a Canvas course from the list, search for the roster section, or type a course "
    "folder name such as ser222_25sc_12345, so GAVEL can name the course folder."
)

_SIS_CLASS_NUMBER = re.compile(r"\d{5}")
_TERM_CODE = re.compile(r"2\d\d[1479]")


def course_key_from_selections(
    course: CanvasCourse | None,
    class_number: str,
    term_code: str,
    section: ClassSection | None,
    manual_folder_name: str = "",
) -> tuple[CourseKey | None, str | None]:
    """``(key, None)`` when the selections name a course folder, else ``(None, why)``.

    Order of preference:

    0. A folder name the user typed (``manual_folder_name``), which always wins.
    1. The Canvas course's SIS code (``2026FallC-X-SER402-87275``), with the
       roster class number choosing the section of a cross-listed course.
    2. The roster term code plus a catalog search result.
    3. Nothing usable: a typed class number alone, a typed Canvas id, or a
       Canvas course without an SIS code (training and renamed courses).
    """
    class_number = class_number.strip()
    term_code = term_code.strip()
    manual_folder_name = manual_folder_name.strip()

    if manual_folder_name:
        try:
            return CourseKey.parse(manual_folder_name), None
        except ValueError as exc:
            return None, str(exc)

    if course is not None:
        try:
            key = CourseKey.from_canvas_course_code(course.course_code, class_number or None)
        except ValueError as exc:
            return None, f"Cannot name the course folder: {exc}."
        if key is not None:
            return key, None

    if section is not None and term_code:
        try:
            return CourseKey.from_roster(term_code, section), None
        except ValueError as exc:
            return None, f"Cannot name the course folder: {exc}."

    if course is not None:
        return None, (
            f"Canvas course '{course.name}' has no ASU course code to name the folder from. "
            "Search for the roster section instead, or type a course folder name at the top of the page."
        )
    return None, NOTHING_TO_NAME_FROM


def roster_key_from_selections(
    course: CanvasCourse | None,
    class_number: str,
    term_code: str,
    section: ClassSection | None,
    manual_folder_name: str = "",
) -> tuple[CourseKey | None, str | None]:
    """The course folder the roster download writes into, named for the roster class.

    Unlike ``course_key_from_selections``, the Canvas course only counts when
    it is the roster's own course, so a roster is never filed under another
    course's subject, term and session. Order of preference:

    0. A folder name the user typed, which always wins.
    1. The Canvas course, when its SIS code carries the class number and its
       term is the roster term. Same course, so the roster shares its folder.
    2. The roster term code plus a catalog search result.
    3. Nothing usable: a typed class number that is not in the Canvas course.
    """
    class_number = class_number.strip()
    term_code = term_code.strip()

    if manual_folder_name.strip() or not class_number:
        return course_key_from_selections(
            course, class_number, term_code, section, manual_folder_name
        )

    if course is not None and _carries_class(course, class_number, term_code):
        return course_key_from_selections(course, class_number, term_code, None)

    if section is not None and term_code:
        return course_key_from_selections(None, class_number, term_code, section)

    if course is None:
        return None, NOTHING_TO_NAME_FROM
    return None, (
        f"Roster class {class_number} is not part of the selected Canvas course, so GAVEL "
        "cannot tell which course folder the roster belongs in. Search for the roster "
        "section, or type a course folder name at the top of the page."
    )


def _carries_class(course: CanvasCourse, class_number: str, term_code: str) -> bool:
    """Whether the course's SIS code lists ``class_number`` in the roster's term.

    Class numbers are reused from term to term, so a valid term code has to
    match the code's term as well.
    """
    code = course.course_code or ""
    parts = [p.strip() for p in code.split("-")]
    if class_number not in (p for p in parts if _SIS_CLASS_NUMBER.fullmatch(p)):
        return False
    if not _TERM_CODE.fullmatch(term_code):
        return True
    key = CourseKey.from_canvas_course_code(code, class_number)
    return (
        key is not None
        and key.year == 2000 + int(term_code[1:3])
        and key.term == TERM_DIGIT_LETTERS[term_code[3]]
    )
