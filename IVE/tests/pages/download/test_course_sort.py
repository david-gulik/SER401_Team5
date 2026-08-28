from __future__ import annotations

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.pages.download.viewmodel import course_sort_key

UPSTREAM_ORDER = [
    CanvasCourse(id=301, name="Software Enterprise: Personal Process", course_code="SER401"),
    CanvasCourse(id=104, name="Data Structures", course_code="CSE205"),
    CanvasCourse(id=209, name="Operating Systems", course_code="ser334"),
    CanvasCourse(id=512, name="Sandbox Course", course_code=None),
    CanvasCourse(id=118, name="Intro to Programming", course_code="CSE110"),
]


def _codes(courses: list[CanvasCourse]) -> list[str]:
    return [c.course_code or c.name for c in courses]


def test_sorts_by_course_code_case_insensitively() -> None:
    ordered = sorted(UPSTREAM_ORDER, key=course_sort_key)

    assert _codes(ordered) == ["CSE110", "CSE205", "Sandbox Course", "ser334", "SER401"]


def test_order_is_stable_across_repeated_invocations() -> None:
    first = sorted(UPSTREAM_ORDER, key=course_sort_key)
    shuffled = list(reversed(UPSTREAM_ORDER))

    assert sorted(shuffled, key=course_sort_key) == first
    assert sorted(first, key=course_sort_key) == first


def test_duplicate_labels_break_ties_on_id() -> None:
    duplicates = [
        CanvasCourse(id=900, name="Capstone", course_code="SER401"),
        CanvasCourse(id=800, name="Capstone", course_code="SER401"),
    ]

    assert [c.id for c in sorted(duplicates, key=course_sort_key)] == [800, 900]


def test_missing_course_code_falls_back_to_name() -> None:
    unlabeled = CanvasCourse(id=1, name="Zebra Studies", course_code=None)
    blank = CanvasCourse(id=2, name="Alpha Studies", course_code="")

    assert course_sort_key(unlabeled)[0] == "zebra studies"
    assert course_sort_key(blank)[0] == "alpha studies"
