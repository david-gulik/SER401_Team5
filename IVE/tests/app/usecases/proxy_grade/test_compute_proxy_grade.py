from __future__ import annotations

from datetime import UTC, datetime

import pytest

from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier
from GAVEL.app.usecases.proxy_grade.compute_proxy_grade import (
    MissingTestResultsError,
    compute_proxy_grade,
)

PASS = (1.0, 1.0)
FAIL = (0.0, 1.0)

# A small mapping used only by these tests.
TOY = ProxyGradeMapping(
    name="toy",
    criteria=(
        Criterion("first", (Tier(2.0, all_of=("Test A", "Test B")), Tier(1.0, all_of=("Test A",)))),
        Criterion("second", (Tier(3.0, any_of=("Test C", "Test D")),)),
    ),
)


def _submission(results: dict[str, tuple[float, float | None]]) -> GradescopeSubmission:
    """Builds a submission from {test name: (score, max_score)}."""
    tests = [
        GradescopeTestScore(name=f"{name} [Hint: ...]", score=score, max_score=max_score)
        for name, (score, max_score) in results.items()
    ]
    return GradescopeSubmission(
        submission_key="submission_test",
        submitter=GradescopeSubmitter(sid="1", email="student@example.com", name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests,
    )


def _all(**overrides: tuple[float, float | None]) -> dict[str, tuple[float, float | None]]:
    results = {"Test A": PASS, "Test B": PASS, "Test C": PASS, "Test D": PASS}
    for key, value in overrides.items():
        results[key.replace("_", " ")] = value
    return results


def test_the_highest_satisfied_tier_wins() -> None:
    result = compute_proxy_grade(_submission(_all()), TOY)
    assert result.criterion_scores == (2.0, 3.0)
    assert result.total_score == 5.0


def test_falls_back_to_a_lower_tier() -> None:
    result = compute_proxy_grade(_submission(_all(Test_B=FAIL)), TOY)
    assert result.criterion_scores == (1.0, 3.0)


def test_no_satisfied_tier_scores_zero() -> None:
    result = compute_proxy_grade(_submission(_all(Test_A=FAIL)), TOY)
    assert result.criterion_scores[0] == 0.0


def test_any_of_needs_only_one_passing_test() -> None:
    one = compute_proxy_grade(_submission(_all(Test_C=FAIL)), TOY)
    neither = compute_proxy_grade(_submission(_all(Test_C=FAIL, Test_D=FAIL)), TOY)
    assert one.criterion_scores[1] == 3.0
    assert neither.criterion_scores[1] == 0.0


def test_partial_credit_on_a_test_is_not_a_pass() -> None:
    result = compute_proxy_grade(_submission(_all(Test_A=(0.5, 1.0))), TOY)
    assert result.criterion_scores[0] == 0.0


def test_a_test_with_no_max_score_is_not_a_pass() -> None:
    result = compute_proxy_grade(_submission(_all(Test_A=(1.0, None))), TOY)
    assert result.criterion_scores[0] == 0.0


def test_missing_tests_are_all_named_in_the_error() -> None:
    with pytest.raises(MissingTestResultsError) as error:
        compute_proxy_grade(_submission({"Test A": PASS}), TOY)
    assert error.value.missing == ("Test B", "Test C", "Test D")


def test_a_missing_test_raises_even_when_it_would_not_change_the_score() -> None:
    # Test A fails, so Test B could never matter, but the mapping still refers to it.
    results = {"Test A": FAIL, "Test C": PASS, "Test D": PASS}
    with pytest.raises(MissingTestResultsError) as error:
        compute_proxy_grade(_submission(results), TOY)
    assert error.value.missing == ("Test B",)
