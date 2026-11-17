from __future__ import annotations

from pathlib import Path

from GAVEL.app.dtos.autograder_run import AutograderRunStatus
from tests.fakes.autograder_runner import (
    FakeAutograderRunner,
    completed,
    crashed,
    per_run,
    timed_out,
)


def test_defaults_to_the_same_completed_run_for_everyone():
    runner = FakeAutograderRunner()

    outcome = runner.run(Path("anon_1"), Path("grader"), timeout_seconds=5)

    assert outcome.status is AutograderRunStatus.COMPLETED
    assert [t.name for t in outcome.tests] == ["Only test"]
    assert runner.calls[0].submission_dir == Path("anon_1")
    assert runner.calls[0].autograder_dir == Path("grader")
    assert runner.calls[0].timeout_seconds == 5
    assert runner.calls[0].run_index == 0


def test_counts_runs_per_submission():
    runner = FakeAutograderRunner()

    runner.run(Path("anon_1"), Path("grader"))
    runner.run(Path("anon_2"), Path("grader"))
    runner.run(Path("anon_1"), Path("grader"))

    assert [(c.submission_dir.name, c.run_index) for c in runner.calls] == [
        ("anon_1", 0),
        ("anon_2", 0),
        ("anon_1", 1),
    ]


def test_a_script_can_single_out_one_submission_and_run():
    def script(name, index):
        if name == "anon_2" and index == 1:
            return timed_out(3.0)
        return completed({"Adds": (2.0, 2.0)})

    runner = FakeAutograderRunner(script)

    assert runner.run(Path("anon_2"), Path("g")).status is AutograderRunStatus.COMPLETED
    assert runner.run(Path("anon_2"), Path("g")).status is AutograderRunStatus.TIMED_OUT
    assert runner.run(Path("anon_1"), Path("g")).status is AutograderRunStatus.COMPLETED


def test_per_run_cycles_the_same_sequence_for_every_submission():
    runner = FakeAutograderRunner(
        per_run([completed({"Adds": (2.0, 2.0)}), crashed("Exited with status 1")])
    )

    statuses = [runner.run(Path("anon_1"), Path("g")).status for _ in range(3)]

    assert statuses == [
        AutograderRunStatus.COMPLETED,
        AutograderRunStatus.CRASHED,
        AutograderRunStatus.COMPLETED,
    ]


def test_builders_fill_in_the_outcome_fields():
    done = completed({"Adds": (1.0, 2.0)}, duration_seconds=4.5, output_tail="ok")
    assert done.tests[0].max_score == 2.0
    assert done.duration_seconds == 4.5
    assert done.output_tail == "ok"
    assert done.error is None

    stopped = timed_out(120.0)
    assert stopped.duration_seconds == 120.0
    assert stopped.error == "Stopped after 120.0 seconds"

    broken = crashed("boom")
    assert broken.tests == ()
    assert broken.error == "boom"
