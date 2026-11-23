from __future__ import annotations

import pytest

from GAVEL.app.dtos.rubric_definition import RubricCriterionDefinition, RubricDefinition
from GAVEL.app.usecases.match_proxy_criteria_to_rubric import (
    UnmatchedProxyCriterionError,
    match_proxy_criteria_to_rubric,
)
from GAVEL.app.usecases.proxy_grade.mappings.ser334_m2 import SER334_M2
from GAVEL.app.usecases.proxy_grade.mappings.ser334_m9 import SER334_M9

# Real SER334 M2 rubric criterion descriptions, as downloaded from the test
# course. "course_insert:: memory" carries the real rubric's own whitespace,
# which differs from the mapping's "course_insert::memory" by one space.
_M2_CRITERION_DESCRIPTIONS = (
    "main menu",
    "memory leaks",
    "course_insert",
    "course_insert:: memory",
    "schedule_print",
    "course_drop",
    "course_drop::memory",
    "schedule_load",
    "schedule_save",
)


def _criterion(cid: str, description: str) -> RubricCriterionDefinition:
    return RubricCriterionDefinition(
        id=cid, description=description, long_description="", points=2.0, ratings=()
    )


def _rubric(descriptions: tuple[str, ...]) -> RubricDefinition:
    return RubricDefinition(
        rubric_id="1448497",
        title="M02.02 [FC21]",
        points_possible=30.0,
        free_form_criterion_comments=False,
        criteria=tuple(
            _criterion(f"c{i}", description) for i, description in enumerate(descriptions)
        ),
    )


def test_matches_every_m2_criterion_against_the_real_rubric() -> None:
    rubric = _rubric(_M2_CRITERION_DESCRIPTIONS)

    matched = match_proxy_criteria_to_rubric(SER334_M2, rubric)

    assert set(matched) == {c.name for c in SER334_M2.criteria}


def test_matches_despite_a_whitespace_difference() -> None:
    rubric = _rubric(_M2_CRITERION_DESCRIPTIONS)

    matched = match_proxy_criteria_to_rubric(SER334_M2, rubric)

    assert matched["course_insert::memory"].description == "course_insert:: memory"


def test_matches_regardless_of_case() -> None:
    rubric = _rubric(("MAIN MENU",) + _M2_CRITERION_DESCRIPTIONS[1:])

    matched = match_proxy_criteria_to_rubric(SER334_M2, rubric)

    assert matched["main menu"].description == "MAIN MENU"


def test_names_every_unmatched_criterion() -> None:
    rubric = _rubric(_M2_CRITERION_DESCRIPTIONS[:-2])

    with pytest.raises(UnmatchedProxyCriterionError) as exc_info:
        match_proxy_criteria_to_rubric(SER334_M2, rubric)

    assert set(exc_info.value.unmatched) == {"schedule_load", "schedule_save"}


def test_two_criteria_that_normalize_the_same_are_rejected_instead_of_silently_merged() -> None:
    rubric = _rubric(("main menu", "Main Menu") + _M2_CRITERION_DESCRIPTIONS[1:])

    with pytest.raises(ValueError, match="ambiguous"):
        match_proxy_criteria_to_rubric(SER334_M2, rubric)


# SER334 M9 rubric ("M09.02", rubric_id 1137679) as downloaded from
# a live course (canvas_course_id 235187, assignment 6603625) and shared by the
# sponsor.
_M9_CRITERIA = (
    ("Read Data: Basic", 2.0),
    ("Read Data: Process(es)", 3.0),
    ("Read Data: Dynamic", 8.0),
    ("SJF: Simulation", 3.0),
    ("SJF: Algorithms", 4.0),
    ("SJF: Output", 3.0),
    ("SJFL: Simulation", 3.0),
    ("SJFL: Algorithms", 6.0),
    ("SJFL: Output", 4.0),
)


def _m9_rubric() -> RubricDefinition:
    return RubricDefinition(
        rubric_id="1137679",
        title="M09.02",
        points_possible=36.0,
        free_form_criterion_comments=False,
        criteria=tuple(
            RubricCriterionDefinition(
                id=f"c{i}", description=description, long_description="", points=points, ratings=()
            )
            for i, (description, points) in enumerate(_M9_CRITERIA)
        ),
    )


def test_matches_every_m9_criterion_against_the_real_rubric() -> None:
    rubric = _m9_rubric()

    matched = match_proxy_criteria_to_rubric(SER334_M9, rubric)

    assert set(matched) == {c.name for c in SER334_M9.criteria}
    assert all(matched[c.name].points == max(t.points for t in c.tiers) for c in SER334_M9.criteria)
