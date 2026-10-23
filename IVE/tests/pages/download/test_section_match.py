"""Class-number check between a myASU roster section and a Canvas course code."""

from __future__ import annotations

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection
from GAVEL.pages.download.section_match import (
    class_numbers_in_course_code,
    course_for_class,
    section_mismatch,
)

SER402 = CanvasCourse(
    id=273116, name="SER 402: Computing Capstone II", course_code="2026FallC-X-SER402-87275"
)
CROSS_LISTED = CanvasCourse(
    id=266960, name="CSE/SER 475", course_code="2026FallC-X-CSE475-SER475-75307-88213"
)
SANDBOX = CanvasCourse(
    id=253450, name="TRN-2026Spring-IVECapstone", course_code="TRN-2026Spring-ivecapstone"
)
NO_CODE = CanvasCourse(id=1, name="Sandbox", course_code=None)
SECTION = ClassSection("87275", "SER", "402", "Computing Capstone II", "Acuna", "TTh 12:00")


@pytest.mark.parametrize(
    ("code", "numbers"),
    [
        ("2026FallC-X-SER402-87275", ("87275",)),
        ("2026FallC-X-CSE475-SER475-75307-88213", ("75307", "88213")),
        ("2021Spring-T-CSE120-11238", ("11238",)),  # older code, no session letter
        ("TRN-2026Spring-ivecapstone", ()),
        ("2026Spring-1770947129529", ()),  # 13 digits is not a class number
        ("", ()),
        (None, ()),
    ],
)
def test_class_numbers_are_the_five_digit_pieces(code, numbers):
    assert class_numbers_in_course_code(code) == numbers


def test_matching_class_number_raises_no_warning():
    assert section_mismatch("87275", SER402) is None


def test_any_section_of_a_cross_listed_course_matches():
    assert section_mismatch("75307", CROSS_LISTED) is None
    assert section_mismatch("88213", CROSS_LISTED) is None


def test_mismatch_names_both_sides():
    text = section_mismatch("12345", SER402)
    assert text is not None
    assert "class 12345" in text
    assert "2026FallC-X-SER402-87275 (class 87275)" in text
    assert "still run" in text  # the ticket wants it clearly non-blocking


def test_mismatch_lists_every_class_of_a_cross_listed_course():
    text = section_mismatch("12345", CROSS_LISTED)
    assert text is not None and "(classes 75307, 88213)" in text


def test_searched_section_enriches_the_roster_side():
    text = section_mismatch("87275", CROSS_LISTED, SECTION)
    assert text is not None and "SER 402 class 87275" in text


@pytest.mark.parametrize("course", [SANDBOX, NO_CODE, None])
def test_nothing_to_compare_against_stays_quiet(course):
    assert section_mismatch("87275", course) is None


def test_no_class_number_stays_quiet():
    assert section_mismatch("", SER402) is None


SPRING_SER402 = CanvasCourse(
    id=255001, name="SER 402 (Spring)", course_code="2026SpringC-X-SER402-87275"
)


def test_course_for_class_finds_the_course_carrying_the_class():
    assert course_for_class("87275", "2267", [SANDBOX, SER402, NO_CODE]) == SER402


def test_course_for_class_matches_any_section_of_a_cross_listed_course():
    assert course_for_class("88213", "2267", [SER402, CROSS_LISTED]) == CROSS_LISTED


def test_course_for_class_is_none_without_a_match():
    assert course_for_class("12345", "2267", [SER402, CROSS_LISTED, SANDBOX]) is None


def test_course_for_class_uses_the_term_to_pick_between_reused_class_numbers():
    courses = [SPRING_SER402, SER402]
    assert course_for_class("87275", "2267", courses) == SER402
    assert course_for_class("87275", "2261", courses) == SPRING_SER402


def test_course_for_class_rejects_a_course_from_another_term():
    assert course_for_class("87275", "2261", [SER402]) is None


@pytest.mark.parametrize("term", ["", "22"])
def test_course_for_class_without_a_usable_term_needs_a_unique_match(term):
    assert course_for_class("87275", term, [SER402]) == SER402
    assert course_for_class("87275", term, [SPRING_SER402, SER402]) is None


def test_course_for_class_needs_a_class_number():
    assert course_for_class("", "2267", [SER402]) is None
