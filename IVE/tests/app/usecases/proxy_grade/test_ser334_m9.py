from __future__ import annotations

from datetime import UTC, datetime

import pytest

from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.usecases.proxy_grade.compute_proxy_grade import compute_proxy_grade
from GAVEL.app.usecases.proxy_grade.mappings.ser334_m9 import SER334_M9

_ALL_TEST_NAMES = list(SER334_M9.test_names())


def _submission(passing: set[str]) -> GradescopeSubmission:
    """Every test in `passing` scores full marks and every other test scores zero."""
    tests = [
        GradescopeTestScore(name=name, score=1.0 if name in passing else 0.0, max_score=1.0)
        for name in _ALL_TEST_NAMES
    ]
    return GradescopeSubmission(
        submission_key="submission_test",
        submitter=GradescopeSubmitter(sid="1", email="student@example.com", name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests,
    )


def test_the_mapping_covers_nine_criteria_worth_thirty_two_points() -> None:
    assert len(SER334_M9.criteria) == 9
    assert len(_ALL_TEST_NAMES) == 15
    assert sum(max(t.points for t in c.tiers) for c in SER334_M9.criteria) == 32.0


def test_all_tests_passing_earns_full_marks() -> None:
    result = compute_proxy_grade(_submission(set(_ALL_TEST_NAMES)), SER334_M9)
    assert result.criterion_scores == (2.0, 2.0, 7.0, 3.0, 4.0, 3.0, 3.0, 4.0, 4.0)
    assert result.total_score == 32.0


def test_all_tests_failing_earns_no_marks() -> None:
    result = compute_proxy_grade(_submission(set()), SER334_M9)
    assert result.total_score == 0.0


# (criterion index, tests that pass, expected points for that criterion)
_TIER_CASES = [
    (0, {"Read Data From File"}, 2.0),
    (1, {"Read Data From File"}, 2.0),
    (2, {"Dynamic Memory Allocation"}, 7.0),
    (3, {"SJF Test Display Ticks"}, 1.5),
    (3, {"SJF Test Simulate Ticks"}, 0.0),
    (3, {"SJF Test Display Ticks", "SJF Test Simulate Ticks"}, 3.0),
    (4, {"SJF Test Algorithm with 2 Processes"}, 2.0),
    (4, {"SJF Test Algorithm with a variable number of Processes"}, 0.0),
    (5, {"SJF Calculate Waiting Time"}, 1.5),
    (5, {"SJF Calculate Turnaround Time", "SJF Calculate Waiting Time"}, 3.0),
    (6, {"SJFL Test Display Ticks"}, 1.5),
    (7, {"SJFL Test Algorithm with 2 Processes"}, 2.0),
    (8, {"SJFL Calculate Estimation Error"}, 2.0),
    (
        8,
        {
            "SJFL Calculate Turnaround Time",
            "SJFL Calculate Waiting Time",
            "SJFL Calculate Estimation Error",
        },
        4.0,
    ),
]


@pytest.mark.parametrize(("index", "passing", "expected"), _TIER_CASES)
def test_each_tier_awards_its_points(index: int, passing: set[str], expected: float) -> None:
    result = compute_proxy_grade(_submission(passing), SER334_M9)
    assert result.criterion_scores[index] == expected
