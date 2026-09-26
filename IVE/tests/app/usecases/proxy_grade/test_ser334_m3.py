from __future__ import annotations

from datetime import UTC, datetime

import pytest

from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.usecases.proxy_grade.compute_proxy_grade import compute_proxy_grade
from GAVEL.app.usecases.proxy_grade.mappings.ser334_m3 import _NAMES, SER334_M3

_ALL_TEST_NAMES = list(SER334_M3.test_names())


def _n(*numbers: str) -> set[str]:
    return {_NAMES[number] for number in numbers}


def _submission(passing: set[str]) -> GradescopeSubmission:
    """Every test in `passing` scores full marks and every other test scores zero."""
    tests = [
        GradescopeTestScore(
            name=f"{name} [Hint: ...]", score=1.0 if name in passing else 0.0, max_score=1.0
        )
        for name in _ALL_TEST_NAMES
    ]
    return GradescopeSubmission(
        submission_key="submission_test",
        submitter=GradescopeSubmitter(sid="1", email="student@example.com", name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests,
    )


def test_the_mapping_covers_nine_criteria() -> None:
    assert len(SER334_M3.criteria) == 9
    assert len(_ALL_TEST_NAMES) == 50  # 53 with the three disabled tests enabled


def test_all_tests_passing_earns_full_marks() -> None:
    result = compute_proxy_grade(_submission(set(_ALL_TEST_NAMES)), SER334_M3)
    assert result.criterion_scores == (4.0, 4.0, 4.0, 4.0, 5.0, 5.0, 5.0, 5.0, 5.0)
    assert result.total_score == 41.0


def test_all_tests_failing_earns_no_marks() -> None:
    result = compute_proxy_grade(_submission(set()), SER334_M3)
    assert result.total_score == 0.0


def test_a_number_is_not_confused_with_a_longer_number_that_contains_it() -> None:
    # Only "11.1)" passes, which contains "1.1)".
    result = compute_proxy_grade(_submission(_n("11.1")), SER334_M3)
    assert result.criterion_scores[0] == 0.0


# (criterion index, test numbers that pass, expected points for that criterion)
_TIER_CASES = [
    (0, ["1.1"], 2.0),
    (0, ["1.1", "1.2"], 4.0),
    (1, ["2.1", "2.2", "2.3", "2.4"], 0.0),
    (1, ["2.1", "2.2", "2.3", "2.4", "2.5"], 2.0),
    (1, ["2.1", "2.2", "2.3", "2.4", "2.5", "3.1", "3.2", "3.3", "3.4"], 4.0),
    (2, ["9.1"], 0.0),
    (2, ["9.1", "9.3"], 2.0),
    (2, ["9.1", "9.2", "9.3"], 4.0),
    (3, ["10.1"], 4.0),
    (4, ["5.1", "5.2", "5.3"], 2.5),
    (4, ["5.1", "5.2", "5.4", "5.5", "10.2", "10.4"], 2.5),
    (4, ["5.1", "5.2"], 0.0),
    (5, ["11.1", "12.1"], 2.5),
    (5, ["11.1"], 0.0),
    (6, ["4.1", "4.2", "4.3", "4.4"], 2.5),
    (6, ["8.1", "8.2", "8.3"], 2.5),
    (6, ["4.1", "4.2", "4.3"], 0.0),
    (7, ["6.2", "6.3", "13.1"], 2.5),
    (7, ["6.1", "6.2"], 0.0),
    (8, ["7.1", "14.1", "14.2"], 2.5),
    (8, ["7.3", "14.3"], 2.5),
    (8, ["7.1", "7.3", "14.1", "14.2", "14.3"], 5.0),
]


@pytest.mark.parametrize(("index", "numbers", "expected"), _TIER_CASES)
def test_each_tier_awards_its_points(index: int, numbers: list[str], expected: float) -> None:
    result = compute_proxy_grade(_submission(_n(*numbers)), SER334_M3)
    assert result.criterion_scores[index] == expected
