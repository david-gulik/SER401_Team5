"""Which course folder the download page's selections point at.

The GUI collects a Canvas course, a roster class number, a term and maybe a
catalog search result. This turns those into one ``CourseKey`` or one
sentence explaining why it cannot, so the view model, the folder preview and
the CLI all agree. Pure: no Qt, no I/O.
"""

from __future__ import annotations

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection
from GAVEL.app.workspace.layout import CourseKey

NOTHING_TO_NAME_FROM = (
    "Select a Canvas course from the list, search for the roster section, or type a course "
    "folder name such as ser222_25sc_12345, so GAVEL can name the course folder."
)


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
