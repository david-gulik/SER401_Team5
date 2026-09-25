"""Applies a proxy-grade mapping to a submission's autograder test results.

The mapping says which tests earn which points on each rubric criterion. This
module only checks whether those tests passed and awards the points, so it has
no knowledge of any particular assignment.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeTestScore
from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier
from GAVEL.app.dtos.proxy_grade_result import ProxyGradeResult


class MissingTestResultsError(ValueError):
    """The submission has no result for one or more tests the mapping refers to."""

    def __init__(self, missing: Sequence[str]) -> None:
        self.missing = tuple(missing)
        super().__init__(f"No test result found matching: {', '.join(self.missing)}")


def _find_test(
    tests: Sequence[GradescopeTestScore], name_substring: str
) -> GradescopeTestScore | None:
    for test in tests:
        if name_substring in test.name:
            return test
    return None


def _passed(test: GradescopeTestScore) -> bool:
    if test.max_score is None:
        return False
    return math.isclose(test.max_score, test.score, abs_tol=0.0001)


def _tier_satisfied(tier: Tier, passed: dict[str, bool]) -> bool:
    if not all(passed[name] for name in tier.all_of):
        return False
    return not tier.any_of or any(passed[name] for name in tier.any_of)


def _criterion_score(criterion: Criterion, passed: dict[str, bool]) -> float:
    for tier in criterion.tiers:
        if _tier_satisfied(tier, passed):
            return tier.points
    return 0.0


def compute_proxy_grade(
    submission: GradescopeSubmission, mapping: ProxyGradeMapping
) -> ProxyGradeResult:
    """Scores a submission against a mapping.

    Raises MissingTestResultsError, naming every missing test at once, when the
    submission lacks a test the mapping refers to. This is checked up front,
    not only when a test happens to be needed, so a mapping that has drifted
    from an assignment's test suite is caught for every submission.
    """
    passed: dict[str, bool] = {}
    missing: list[str] = []
    for name in mapping.test_names():
        test = _find_test(submission.tests, name)
        if test is None:
            missing.append(name)
        else:
            passed[name] = _passed(test)
    if missing:
        raise MissingTestResultsError(missing)

    criterion_scores = tuple(_criterion_score(c, passed) for c in mapping.criteria)
    return ProxyGradeResult(criterion_scores=criterion_scores, total_score=sum(criterion_scores))
