from __future__ import annotations

from GAVEL.app.dtos.autograder_run import AutograderRunOutcome, AutograderRunStatus
from GAVEL.app.dtos.gradescope import GradescopeTestScore


def test_only_a_completed_run_counts_as_completed():
    done = AutograderRunOutcome(
        status=AutograderRunStatus.COMPLETED,
        duration_seconds=2.0,
        tests=(GradescopeTestScore(name="Adds", score=1.0, max_score=1.0),),
    )
    stopped = AutograderRunOutcome(status=AutograderRunStatus.TIMED_OUT, duration_seconds=300.0)
    broken = AutograderRunOutcome(status=AutograderRunStatus.CRASHED, duration_seconds=0.2)

    assert done.completed
    assert not stopped.completed
    assert not broken.completed


def test_a_run_that_did_not_complete_has_no_scores_by_default():
    stopped = AutograderRunOutcome(status=AutograderRunStatus.TIMED_OUT, duration_seconds=300.0)

    assert stopped.tests == ()
    assert stopped.output_tail == ""
    assert stopped.error is None
