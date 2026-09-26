from __future__ import annotations

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection
from GAVEL.app.workspace.layout import CourseKey
from GAVEL.app.workspace.resolve import NOTHING_TO_NAME_FROM, course_key_from_selections

SIS_COURSE = CanvasCourse(id=1, name="SER 402", course_code="2026FallC-X-SER402-87275-87276")
TRAINING_COURSE = CanvasCourse(id=2, name="IVE Capstone", course_code="TRN-2026Spring")
SECTION = ClassSection("11111", "SER", "401", "Capstone I", "Gary", "TTh", session="C")


def test_canvas_code_alone_uses_its_first_class_number():
    key, why = course_key_from_selections(SIS_COURSE, "", "", None)
    assert why is None
    assert key == CourseKey("SER", "402", 2026, "f", "c", "87275")


def test_roster_class_number_picks_the_section_of_a_cross_listed_course():
    key, _ = course_key_from_selections(SIS_COURSE, "87276", "", None)
    assert key is not None and key.class_number == "87276"


def test_canvas_code_beats_the_roster_section():
    key, _ = course_key_from_selections(SIS_COURSE, "11111", "2267", SECTION)
    assert key is not None and key.subject == "SER" and key.catalog_number == "402"
    assert key.class_number == "11111"


def test_roster_section_when_canvas_has_no_sis_code():
    key, why = course_key_from_selections(TRAINING_COURSE, "11111", "2267", SECTION)
    assert why is None
    assert key == CourseKey("SER", "401", 2026, "f", "c", "11111")


def test_roster_section_without_canvas_course():
    key, why = course_key_from_selections(None, "11111", "2267", SECTION)
    assert why is None
    assert key is not None and key.folder_name == "ser401_26fc_11111"


@pytest.mark.parametrize(
    ("course", "class_number", "term", "section"),
    [
        (None, "", "", None),
        (None, "12345", "2267", None),  # typed class number only
        (None, "", "2267", None),
        (None, "11111", "", SECTION),  # section without a term
    ],
)
def test_nothing_usable_explains_itself(course, class_number, term, section):
    key, why = course_key_from_selections(course, class_number, term, section)
    assert key is None
    assert why == NOTHING_TO_NAME_FROM


def test_canvas_course_without_sis_code_and_no_section_names_the_course():
    key, why = course_key_from_selections(TRAINING_COURSE, "12345", "2267", None)
    assert key is None
    assert why is not None and "IVE Capstone" in why and "no ASU course code" in why


def test_bad_class_number_is_reported_not_raised():
    key, why = course_key_from_selections(SIS_COURSE, "12a", "", None)
    assert key is None
    assert why is not None and "digits only" in why


def test_bad_term_code_is_reported_not_raised():
    key, why = course_key_from_selections(None, "11111", "9999", SECTION)
    assert key is None
    assert why is not None and "term code" in why


class TestManualName:
    def test_typed_name_wins_over_everything(self):
        key, why = course_key_from_selections(
            SIS_COURSE, "87276", "2267", SECTION, "cse110_25ua_55555"
        )
        assert why is None
        assert key == CourseKey("CSE", "110", 2025, "u", "a", "55555")

    def test_typed_name_rescues_a_training_course(self):
        key, why = course_key_from_selections(TRAINING_COURSE, "", "", None, "ser401_26f_99999")
        assert why is None
        assert key is not None and key.folder_name == "ser401_26f_99999"

    def test_malformed_typed_name_is_reported(self):
        key, why = course_key_from_selections(SIS_COURSE, "", "", None, "my course")
        assert key is None
        assert why is not None
        assert why.startswith("'my course' is not a valid course folder name")
        assert "three parts joined by underscores" in why
        assert "like ser222_25sc_12345" in why

    def test_blank_typed_name_is_ignored(self):
        key, _ = course_key_from_selections(SIS_COURSE, "", "", None, "   ")
        assert key is not None and key.class_number == "87275"

    def test_nothing_message_mentions_typing_a_name(self):
        assert "type a course folder name" in NOTHING_TO_NAME_FROM
