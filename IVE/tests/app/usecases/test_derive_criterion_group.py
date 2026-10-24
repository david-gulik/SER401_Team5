from __future__ import annotations

from GAVEL.app.usecases.derive_criterion_group import derive_criterion_group


def test_a_criterion_with_no_separator_is_its_own_group() -> None:
    assert derive_criterion_group("schedule_print") == "schedule_print"


def test_a_criterion_name_is_split_on_the_separator() -> None:
    assert derive_criterion_group("course_insert::memory") == "course_insert"


def test_criteria_sharing_a_prefix_share_a_group() -> None:
    insert_memory = derive_criterion_group("course_insert::memory")
    drop_memory = derive_criterion_group("course_drop::memory")

    assert insert_memory == "course_insert"
    assert drop_memory == "course_drop"
    assert insert_memory != drop_memory


def test_only_the_first_separator_splits_the_name() -> None:
    assert derive_criterion_group("a::b::c") == "a"


def test_whitespace_around_the_group_name_is_stripped() -> None:
    assert derive_criterion_group(" course_insert ::memory") == "course_insert"
