"""What a stability check found: how consistently an autograder scored each test.

A check runs one autograder on every submission several times. The report
keeps every execution, then rolls them up per test and, when a proxy mapping
is known, per rubric criterion. For one submission and one test, the "usual"
result is the one most runs gave; a run that gave something else, or no
result at all, counts against agreement.

A run that timed out or crashed gives no result for any test. That is a fact
about the submission's execution rather than about one test, so it is
reported on the submission, and a test is judged Pass or Changed on the runs
that did complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from GAVEL.app.dtos.autograder_run import AutograderRunStatus
from GAVEL.app.dtos.gradescope import GradescopeTestScore


class StabilityState(Enum):
    """Pass: the same result on every completed run. Changed: the result
    differed between runs. Broke: no result at all, because every run timed
    out or crashed. Broke outranks Changed."""

    PASS = "pass"
    CHANGED = "changed"
    BROKE = "broke"


_RANK = {StabilityState.PASS: 0, StabilityState.CHANGED: 1, StabilityState.BROKE: 2}


def severity(state: StabilityState) -> int:
    """0 for Pass, 1 for Changed, 2 for Broke; higher is worse."""
    return _RANK[state]


def worst(states: tuple[StabilityState, ...]) -> StabilityState:
    return max(states, key=severity, default=StabilityState.PASS)


@dataclass(frozen=True)
class ResultSeen:
    """One distinct result and the runs (1-based) that produced it.

    A ``score`` of None means those runs produced no result for the item.
    """

    score: float | None
    max_score: float | None
    runs: tuple[int, ...]
    output: str | None = None


@dataclass(frozen=True)
class SubmissionItemStability:
    """One submission's agreement on one test or criterion."""

    submission: str
    state: StabilityState
    runs_agreed: int
    runs_total: int
    # The usual result first, then the others by how many runs gave them;
    # runs with no result come last.
    results: tuple[ResultSeen, ...]

    @property
    def usual(self) -> ResultSeen | None:
        for result in self.results:
            if result.score is not None:
                return result
        return None

    @property
    def runs_broke(self) -> int:
        return sum(len(r.runs) for r in self.results if r.score is None)


@dataclass(frozen=True)
class ItemStability:
    """A test, or a rubric criterion, across every submission and run."""

    name: str
    state: StabilityState
    runs_agreed: int
    runs_total: int
    # Executions that produced no result for this item at all.
    runs_broke: int
    submissions_total: int
    # Only the submissions whose completed runs did not all agree, worst first.
    affected: tuple[SubmissionItemStability, ...]
    # For a criterion: the tests the proxy mapping builds it from.
    built_from: tuple[str, ...] = ()

    @property
    def submissions_affected(self) -> int:
        return len(self.affected)

    @property
    def agreement(self) -> float:
        return self.runs_agreed / self.runs_total if self.runs_total else 0.0

    @property
    def runs_changed(self) -> int:
        return self.runs_total - self.runs_agreed - self.runs_broke


@dataclass(frozen=True)
class SubmissionStability:
    name: str
    runs_completed: int
    runs_timed_out: int
    runs_crashed: int
    errors: tuple[str, ...]

    @property
    def runs_broke(self) -> int:
        return self.runs_timed_out + self.runs_crashed

    @property
    def runs_total(self) -> int:
        return self.runs_completed + self.runs_broke


@dataclass(frozen=True)
class ExecutionRecord:
    """One run of the autograder on one submission."""

    submission: str
    run: int
    status: AutograderRunStatus
    duration_seconds: float
    scores: tuple[GradescopeTestScore, ...] = ()
    error: str | None = None
    output_tail: str = ""

    @property
    def completed(self) -> bool:
        return self.status is AutograderRunStatus.COMPLETED


@dataclass(frozen=True)
class StabilityReport:
    course: str
    module_number: int
    autograder: str
    runs_requested: int
    runs_completed: int
    cancelled: bool
    workers: int
    timeout_seconds: float | None
    started_at: str
    finished_at: str
    submissions: tuple[SubmissionStability, ...]
    tests: tuple[ItemStability, ...]
    criteria: tuple[ItemStability, ...]
    mapping_name: str | None
    executions: tuple[ExecutionRecord, ...]

    @property
    def broken_submissions(self) -> tuple[SubmissionStability, ...]:
        """Submissions with at least one run that timed out or crashed."""
        return tuple(s for s in self.submissions if s.runs_broke)

    @property
    def verdict(self) -> StabilityState:
        if self.broken_submissions:
            return StabilityState.BROKE
        return worst(tuple(test.state for test in self.tests))

    def tests_in(self, state: StabilityState) -> tuple[ItemStability, ...]:
        return tuple(test for test in self.tests if test.state is state)

    @property
    def executions_total(self) -> int:
        return len(self.executions)

    @property
    def submissions_affected(self) -> int:
        """Submissions that changed a result or broke on at least one run."""
        names = {entry.submission for test in self.tests for entry in test.affected}
        names.update(s.name for s in self.broken_submissions)
        return len(names)
