from __future__ import annotations

import pytest

from GAVEL.app.dtos.rubric_definition import RubricCriterionDefinition, RubricDefinition
from GAVEL.app.usecases.match_proxy_criteria_to_rubric import (
    UnmatchedProxyCriterionError,
    match_proxy_criteria_to_rubric,
)
from GAVEL.app.usecases.proxy_grade.mappings.ser334_m2 import SER334_M2

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
