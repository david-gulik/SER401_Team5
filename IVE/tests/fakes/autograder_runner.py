"""An in-memory AutograderRunner whose outcomes a test scripts ahead of time."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.autograder_run import AutograderRunOutcome, AutograderRunStatus
from GAVEL.app.dtos.gradescope import GradescopeTestScore
from GAVEL.app.ports.autograder_runner import AutograderRunner

# Decides the outcome of a run from the submission folder's name and how many
# runs that submission has already had (0 for its first).
OutcomeScript = Callable[[str, int], AutograderRunOutcome]


@dataclass(frozen=True)
class RunCall:
    submission_dir: Path
    autograder_dir: Path
    timeout_seconds: float | None
    run_index: int


class FakeAutograderRunner(AutograderRunner):
    """Returns scripted outcomes and remembers every call.

    With no script every run completes with ``default``'s scores. A script can
    make one submission flaky, another hang, and so on, keyed by folder name
    and run index.
    """

    def __init__(
        self,
        script: OutcomeScript | None = None,
        default: AutograderRunOutcome | None = None,
    ) -> None:
        self._script = script
        self._default = default if default is not None else completed({"Only test": (1.0, 1.0)})
        self.calls: list[RunCall] = []
        self._runs_seen: Counter[str] = Counter()

    def run(
        self,
        submission_dir: Path,
        autograder_dir: Path,
        timeout_seconds: float | None = None,
    ) -> AutograderRunOutcome:
        name = Path(submission_dir).name
        index = self._runs_seen[name]
        self._runs_seen[name] += 1
        self.calls.append(
            RunCall(Path(submission_dir), Path(autograder_dir), timeout_seconds, index)
        )
        if self._script is not None:
            return self._script(name, index)
        return self._default


def completed(
    scores: Mapping[str, tuple[float, float]],
    duration_seconds: float = 1.0,
    output_tail: str = "",
) -> AutograderRunOutcome:
    """A completed run; ``scores`` maps test name to (score, max_score)."""
    tests = tuple(
        GradescopeTestScore(name=name, score=score, max_score=max_score)
        for name, (score, max_score) in scores.items()
    )
    return AutograderRunOutcome(
        status=AutograderRunStatus.COMPLETED,
        duration_seconds=duration_seconds,
        tests=tests,
        output_tail=output_tail,
    )


def timed_out(timeout_seconds: float = 300.0) -> AutograderRunOutcome:
    return AutograderRunOutcome(
        status=AutograderRunStatus.TIMED_OUT,
        duration_seconds=timeout_seconds,
        error=f"Stopped after {timeout_seconds} seconds",
    )


def crashed(
    error: str = "Exited with status 1", duration_seconds: float = 0.5
) -> AutograderRunOutcome:
    return AutograderRunOutcome(
        status=AutograderRunStatus.CRASHED,
        duration_seconds=duration_seconds,
        error=error,
    )


def per_run(outcomes: Sequence[AutograderRunOutcome]) -> OutcomeScript:
    """A script that gives every submission the same sequence of outcomes, cycling."""

    def script(_name: str, index: int) -> AutograderRunOutcome:
        return outcomes[index % len(outcomes)]

    return script
