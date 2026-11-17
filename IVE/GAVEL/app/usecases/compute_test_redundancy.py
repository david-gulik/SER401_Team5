from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeTestScore
from GAVEL.app.usecases.compute_r_squared import compute_r_squared


@dataclass(frozen=True)
class PairRedundancy:
    """How closely two autograder tests' pass/fail outcomes track each other.
    A high r_squared means the tests tend to pass and fail together across
    submissions (which is a sign that one of the pair may be redundant).
    """

    test_a: str
    test_b: str
    r_squared: float


def _passed(test: GradescopeTestScore) -> float:
    if test.max_score is None:
        return 0.0
    return 1.0 if math.isclose(test.max_score, test.score, abs_tol=0.0001) else 0.0


def compute_test_redundancy(
    submissions: Sequence[GradescopeSubmission],
) -> tuple[PairRedundancy, ...]:
    """r-squared between every pair of autograder tests' pass/fail outcomes.
    Every submission reports the same set of tests. Raises ValueError and names the submission if a submission's tests don't
    match the first submission's. A pair with zero variance on either side
    (like a test that every submission has passed) has no defined r-squared and is
    left out of the result.
    """
    if len(submissions) < 2:
        raise ValueError("At least two submissions are required.")

    test_names = sorted(test.name for test in submissions[0].tests)
    outcomes_by_test: dict[str, list[float]] = {name: [] for name in test_names}

    for submission in submissions:
        names_here = sorted(test.name for test in submission.tests)
        if names_here != test_names:
            raise ValueError(
                f"Submission {submission.submission_key} does not report the same tests as the first submission."
            )
        passed_by_name = {test.name: _passed(test) for test in submission.tests}
        for name in test_names:
            outcomes_by_test[name].append(passed_by_name[name])

    pairs: list[PairRedundancy] = []
    for i, test_a in enumerate(test_names):
        for test_b in test_names[i + 1 :]:
            try:
                r_squared = compute_r_squared(outcomes_by_test[test_a], outcomes_by_test[test_b])
            except ValueError:
                continue
            pairs.append(PairRedundancy(test_a, test_b, r_squared))

    return tuple(pairs)
