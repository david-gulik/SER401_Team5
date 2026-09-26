from __future__ import annotations

from datetime import UTC, datetime

import pytest

from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.usecases.proxy_grade.compute_proxy_grade import (
    # MissingTestResultsError,
    compute_proxy_grade,
)
from GAVEL.app.usecases.proxy_grade.mappings.ser334_m2 import SER334_M2

# Every test name the mapping refers to.
_ALL_TEST_NAMES = list(SER334_M2.test_names())

_INSERT = [f"Insert Course {n}" for n in range(1, 8)]
_REMOVE = [f"Remove Course {n}" for n in range(1, 5)]


def _submission(passing: set[str], names: list[str] | None = None) -> GradescopeSubmission:
    """Every test in `passing` scores full marks and every other test scores zero."""
    tests = [
        GradescopeTestScore(
            name=f"{name} [Hint: ...]",
            score=1.0 if name in passing else 0.0,
            max_score=1.0,
        )
        for name in (names if names is not None else _ALL_TEST_NAMES)
    ]
    return GradescopeSubmission(
        submission_key="submission_test",
        submitter=GradescopeSubmitter(sid="1", email="student@example.com", name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests,
    )


def test_the_mapping_covers_nine_criteria_worth_thirty_points() -> None:
    assert len(SER334_M2.criteria) == 9
    assert len(_ALL_TEST_NAMES) == 24  # 25 with "Memory Allocation 6" enabled
    assert sum(max(t.points for t in c.tiers) for c in SER334_M2.criteria) == 30.0


def test_all_tests_passing_earns_full_marks() -> None:
    result = compute_proxy_grade(_submission(set(_ALL_TEST_NAMES)), SER334_M2)
    assert result.criterion_scores == (2.0, 2.0, 7.0, 2.0, 2.0, 5.0, 2.0, 4.0, 4.0)
    assert result.total_score == 30.0


def test_all_tests_failing_earns_no_marks() -> None:
    result = compute_proxy_grade(_submission(set()), SER334_M2)
    assert result.criterion_scores == (0.0,) * 9
    assert result.total_score == 0.0


def test_mixed_results_hit_the_middle_tiers() -> None:
    passing = {
        "Main Menu 1",
        "Memory Allocation 3",
        "Insert Course 1",
        "Insert Course 2",
        "Insert Course 4",
        "Memory Allocation 1",
        "Memory Allocation 2",
        "Schedule Print",
        "Remove Course 1",
        "Remove Course 2",
        "Remove Course 3",
        "Memory Allocation 5",
        "Load File 1",
        "Save File 1",
        "Save File 2",
    }
    result = compute_proxy_grade(_submission(passing), SER334_M2)
    # With "Memory Allocation 6" enabled, the seventh score is 1.0 and the total is 19.0.
    assert result.criterion_scores == (1.0, 1.0, 3.5, 2.0, 2.0, 2.5, 2.0, 2.0, 4.0)
    assert result.total_score == 20.0


# (criterion index, tests that pass, expected points for that criterion)
_TIER_CASES = [
    (0, set(), 0.0),
    (0, {"Main Menu 1"}, 1.0),
    (0, {"Main Menu 2"}, 0.0),
    (0, {"Main Menu 1", "Main Menu 2"}, 2.0),
    (1, {"Memory Allocation 3"}, 1.0),
    (1, {"Memory Allocation 4"}, 0.0),
    (1, {"Memory Allocation 3", "Memory Allocation 4"}, 2.0),
    (2, {"Insert Course 1"}, 1.75),
    (2, {"Insert Course 1", "Insert Course 2"}, 1.75),
    (2, {"Insert Course 1", "Insert Course 2", "Insert Course 4"}, 3.5),
    (2, set(_INSERT), 7.0),
    (2, set(_INSERT) - {"Insert Course 1"}, 0.0),
    (3, {"Memory Allocation 1"}, 1.0),
    (3, {"Memory Allocation 2"}, 0.0),
    (3, {"Memory Allocation 1", "Memory Allocation 2"}, 2.0),
    (4, set(), 0.0),
    (4, {"Schedule Print"}, 2.0),
    (5, {"Remove Course 1"}, 1.25),
    (5, {"Remove Course 1", "Remove Course 2", "Remove Course 3"}, 2.5),
    (5, set(_REMOVE), 5.0),
    (5, set(_REMOVE) - {"Remove Course 1"}, 0.0),
    (6, {"Memory Allocation 5"}, 2.0),  # 1.0 with "Memory Allocation 6" enabled
    # (6, {"Memory Allocation 6"}, 0.0),
    # (6, {"Memory Allocation 5", "Memory Allocation 6"}, 2.0),
    (7, {"Load File 1"}, 2.0),
    (7, {"Load File 1", "Load File 2"}, 2.0),
    (7, {"Load File 1", "Load File 2", "Load File 3"}, 4.0),
    (8, {"Save File 1"}, 2.0),
    (8, {"Save File 2"}, 0.0),
    (8, {"Save File 1", "Save File 2"}, 4.0),
]


@pytest.mark.parametrize(("index", "passing", "expected"), _TIER_CASES)
def test_each_tier_awards_its_points(index: int, passing: set[str], expected: float) -> None:
    result = compute_proxy_grade(_submission(passing), SER334_M2)
    assert result.criterion_scores[index] == expected


# def test_a_suite_without_memory_allocation_6_is_reported_by_name() -> None:
#     names = [name for name in _ALL_TEST_NAMES if name != "Memory Allocation 6"]
#     with pytest.raises(MissingTestResultsError) as error:
#         compute_proxy_grade(_submission(set(names), names), SER334_M2)
#     assert error.value.missing == ("Memory Allocation 6",)
