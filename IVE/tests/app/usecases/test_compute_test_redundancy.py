from __future__ import annotations

from datetime import UTC, datetime

import pytest

from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.usecases.compute_test_redundancy import PairRedundancy, compute_test_redundancy


def _submission(key: str, passing: set[str], all_tests: set[str]) -> GradescopeSubmission:
    tests = [
        GradescopeTestScore(name=name, score=1.0 if name in passing else 0.0, max_score=1.0)
        for name in all_tests
    ]
    return GradescopeSubmission(
        submission_key=key,
        submitter=GradescopeSubmitter(sid="1", email="student@example.com", name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests,
    )


def test_fewer_than_two_submissions_is_rejected() -> None:
    with pytest.raises(ValueError):
        compute_test_redundancy([_submission("s1", {"A"}, {"A"})])


def test_a_submission_with_different_tests_is_rejected() -> None:
    submissions = [
        _submission("s1", {"A"}, {"A", "B"}),
        _submission("s2", {"A"}, {"A", "C"}),
    ]

    with pytest.raises(ValueError, match="s2"):
        compute_test_redundancy(submissions)


def test_tests_that_always_agree_score_a_perfect_pair() -> None:
    all_tests = {"A", "B", "C"}
    submissions = [
        _submission("s1", {"A", "B", "C"}, all_tests),
        _submission("s2", {"A", "B"}, all_tests),
        _submission("s3", {"C"}, all_tests),
        _submission("s4", set(), all_tests),
    ]

    pairs = compute_test_redundancy(submissions)

    assert set(pairs) == {
        PairRedundancy("A", "B", 1.0),
        PairRedundancy("A", "C", 0.0),
        PairRedundancy("B", "C", 0.0),
    }


def test_a_test_every_submission_passes_has_no_defined_pair() -> None:
    all_tests = {"A", "B", "D"}
    submissions = [
        _submission("s1", {"A", "B", "D"}, all_tests),
        _submission("s2", {"A", "D"}, all_tests),
        _submission("s3", {"D"}, all_tests),
        _submission("s4", {"D"}, all_tests),
    ]

    pairs = compute_test_redundancy(submissions)

    assert all("D" not in (pair.test_a, pair.test_b) for pair in pairs)
    assert len(pairs) == 1
