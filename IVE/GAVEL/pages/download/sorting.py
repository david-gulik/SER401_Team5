"""Ordering rules for the download page's selection dropdowns.

Kept free of PyQt imports so the rules stay unit-testable without a GUI
dependency; the view model applies them when it publishes state.
"""

from __future__ import annotations

from GAVEL.app.dtos.canvas_course import CanvasCourse


def course_sort_key(course: CanvasCourse) -> tuple[str, str, int]:
    """Ordering rule for Canvas course selection entries.

    Sorts on the text the dropdown actually shows - the course code when Canvas
    supplies one, the course name otherwise - then on name and id so the order is
    total and comes out identical on every reload.
    """
    primary = (course.course_code or course.name or "").strip().casefold()
    return (primary, (course.name or "").strip().casefold(), course.id)
