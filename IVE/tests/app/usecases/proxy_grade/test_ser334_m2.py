from __future__ import annotations

from datetime import UTC, datetime

import pytest

from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.usecases.proxy_grade.ser334_m2 import compute_proxy_grade

# The 25 distinct test names compute_proxy_grade looks up, taken from the real
# assignment's test suite (ser334_config_m2.json), not from any student
# submission.
_ALL_TEST_NAMES = [
    "Main Menu 1",
    "Main Menu 2",
    "Memory Allocation 1",
    "Memory Allocation 2",
    "Memory Allocation 3",
    "Memory Allocation 4",
    "Memory Allocation 5",
    "Memory Allocation 6",
    "Insert Course 1",
    "Insert Course 2",
    "Insert Course 3",
    "Insert Course 4",
    "Insert Course 5",
    "Insert Course 6",
    "Insert Course 7",
    "Schedule Print",
    "Remove Course 1",
    "Remove Course 2",
    "Remove Course 3",
    "Remove Course 4",
    "Load File 1",
    "Load File 2",
    "Load File 3",
    "Save File 1",
    "Save File 2",
]


def _submission(passing: set[str]) -> GradescopeSubmission:
    """Builds a submission where every test in `passing` scores full marks and every other test scores zero."""
    tests = [
        GradescopeTestScore(
            name=f"{name} [Hint: ...]",
            score=1.0 if name in passing else 0.0,
            max_score=1.0,
        )
        for name in _ALL_TEST_NAMES
    ]
    return GradescopeSubmission(
        submission_key="submission_test",
        submitter=GradescopeSubmitter(sid="1", email="student@example.com", name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests,
    )


def test_all_tests_passing_earns_full_marks() -> None:
    result = compute_proxy_grade(_submission(set(_ALL_TEST_NAMES)))
    assert result.criterion_scores == (2.0, 2.0, 7.0, 2.0, 2.0, 5.0, 2.0, 4.0, 4.0)
    assert result.total_score == 30.0


def test_all_tests_failing_earns_no_marks() -> None:
    result = compute_proxy_grade(_submission(set()))
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
    result = compute_proxy_grade(_submission(passing))
    assert result.criterion_scores == (1.0, 1.0, 3.5, 2.0, 2.0, 2.5, 1.0, 2.0, 4.0)
    assert result.total_score == 19.0


def test_missing_test_result_raises() -> None:
    incomplete = GradescopeSubmission(
        submission_key="submission_incomplete",
        submitter=GradescopeSubmitter(sid="1", email="student@example.com", name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=[],
    )
    with pytest.raises(ValueError):
        compute_proxy_grade(incomplete)
