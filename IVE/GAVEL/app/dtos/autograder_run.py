from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from GAVEL.app.dtos.gradescope import GradescopeTestScore


class AutograderRunStatus(Enum):
    """How one execution of an autograder on one submission ended."""

    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    CRASHED = "crashed"


@dataclass(frozen=True)
class AutograderRunOutcome:
    """What one execution of an autograder produced.

    ``tests`` holds a score per test only when the run completed; a timed-out
    or crashed run has no scores. ``output_tail`` is the end of whatever the
    autograder printed, kept so a failure can be traced without rerunning it.
    ``error`` says why a run did not complete.
    """

    status: AutograderRunStatus
    duration_seconds: float
    tests: tuple[GradescopeTestScore, ...] = ()
    output_tail: str = ""
    error: str | None = None

    @property
    def completed(self) -> bool:
        return self.status is AutograderRunStatus.COMPLETED
