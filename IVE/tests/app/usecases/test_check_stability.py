from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from GAVEL.app.dtos.autograder_run import AutograderRunStatus
from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier
from GAVEL.app.dtos.stability import ResultSeen, StabilityState
from GAVEL.app.usecases.check_stability import (
    CheckStabilityRequest,
    CheckStabilityUseCase,
    NoSubmissionsError,
)
from tests.fakes.autograder_runner import (
    FakeAutograderRunner,
    completed,
    crashed,
    timed_out,
)

FULL = {"Adds two numbers": (2.0, 2.0), "Prints the total": (1.0, 1.0)}
ADDS_FAILED = {"Adds two numbers": (0.0, 2.0), "Prints the total": (1.0, 1.0)}

MAPPING = ProxyGradeMapping(
    name="test_m1",
    criteria=(
        Criterion("adding", (Tier(2.0, all_of=("Adds two numbers",)),)),
        Criterion("printing", (Tier(1.0, all_of=("Prints the total",)),)),
    ),
)


def _submissions(tmp_path: Path, names=("anon_1", "anon_2", "anon_3")) -> tuple[Path, ...]:
    folder = tmp_path / "extracted"
    folder.mkdir()
    for name in names:
        (folder / name).mkdir()
        (folder / name / "answer.txt").write_text("42", encoding="utf-8")
    (folder / "submission_metadata.yml").write_text("{}", encoding="utf-8")
    return tuple(folder / name for name in names)


def _request(tmp_path: Path, runs: int = 4, **overrides) -> CheckStabilityRequest:
    fields = {
        "course": "ser334_25fc_82931",
        "module_number": 9,
        "autograder": "ser334_m9_grader",
        "autograder_dir": tmp_path / "grader",
        "submission_dirs": _submissions(tmp_path),
        "runs": runs,
    }
    fields.update(overrides)
    return CheckStabilityRequest(**fields)


def _ticking_clock():
    times = iter([datetime(2026, 11, 16, 14, 0, 0), datetime(2026, 11, 16, 14, 23, 36)])
    return lambda: next(times)


def _test(report, name):
    [item] = [t for t in report.tests if t.name == name]
    return item


def test_a_deterministic_autograder_passes_every_test(tmp_path):
    runner = FakeAutograderRunner(default=completed(FULL))

    report = CheckStabilityUseCase(runner, _ticking_clock()).execute(_request(tmp_path))

    assert report.verdict is StabilityState.PASS
    assert [t.name for t in report.tests] == ["Adds two numbers", "Prints the total"]
    for test in report.tests:
        assert test.state is StabilityState.PASS
        assert (test.runs_agreed, test.runs_total) == (12, 12)
        assert test.agreement == 1.0
        assert test.affected == ()
        assert test.submissions_total == 3
    assert report.runs_completed == 4
    assert not report.cancelled
    assert report.executions_total == 12
    assert report.submissions_affected == 0
    assert report.started_at == "2026-11-16T14:00:00"
    assert report.finished_at == "2026-11-16T14:23:36"
    assert len(runner.calls) == 12
    assert {c.autograder_dir for c in runner.calls} == {tmp_path / "grader"}


def test_a_flaky_test_is_changed_with_its_real_rate(tmp_path):
    def script(name, index):
        if name == "anon_2" and index in (1, 3):
            return completed(ADDS_FAILED)
        return completed(FULL)

    report = CheckStabilityUseCase(FakeAutograderRunner(script)).execute(_request(tmp_path))

    adds = _test(report, "Adds two numbers")
    assert adds.state is StabilityState.CHANGED
    assert (adds.runs_agreed, adds.runs_total) == (10, 12)
    assert adds.submissions_affected == 1
    [entry] = adds.affected
    assert entry.submission == "anon_2"
    assert entry.state is StabilityState.CHANGED
    assert (entry.runs_agreed, entry.runs_total) == (2, 4)
    assert entry.results == (
        ResultSeen(score=2.0, max_score=2.0, runs=(1, 3)),
        ResultSeen(score=0.0, max_score=2.0, runs=(2, 4)),
    )
    assert entry.usual == ResultSeen(score=2.0, max_score=2.0, runs=(1, 3))
    assert _test(report, "Prints the total").state is StabilityState.PASS
    assert report.verdict is StabilityState.CHANGED
    assert report.submissions_affected == 1


def test_the_usual_result_is_the_one_most_runs_gave(tmp_path):
    def script(name, index):
        return completed(FULL) if index == 0 else completed(ADDS_FAILED)

    report = CheckStabilityUseCase(FakeAutograderRunner(script)).execute(_request(tmp_path))

    [entry] = [e for e in _test(report, "Adds two numbers").affected if e.submission == "anon_1"]
    assert entry.usual is not None
    assert entry.usual.score == 0.0
    assert entry.usual.runs == (2, 3, 4)
    assert (entry.runs_agreed, entry.runs_total) == (3, 4)


def test_a_timed_out_run_breaks_every_test_and_outranks_changed(tmp_path):
    def script(name, index):
        if name == "anon_3" and index == 0:
            return timed_out(300.0)
        if name == "anon_2" and index == 1:
            return completed(ADDS_FAILED)
        return completed(FULL)

    report = CheckStabilityUseCase(FakeAutograderRunner(script)).execute(_request(tmp_path))

    adds = _test(report, "Adds two numbers")
    assert adds.state is StabilityState.BROKE
    assert (adds.runs_agreed, adds.runs_total) == (10, 12)
    assert [e.submission for e in adds.affected] == ["anon_3", "anon_2"]
    broke = adds.affected[0]
    assert broke.state is StabilityState.BROKE
    assert (broke.runs_agreed, broke.runs_total) == (3, 4)
    assert broke.results[-1] == ResultSeen(score=None, max_score=None, runs=(1,))
    assert _test(report, "Prints the total").state is StabilityState.BROKE
    assert report.verdict is StabilityState.BROKE

    [anon_3] = [s for s in report.submissions if s.name == "anon_3"]
    assert (anon_3.runs_completed, anon_3.runs_timed_out, anon_3.runs_crashed) == (3, 1, 0)
    assert anon_3.errors == ("Stopped after 300.0 seconds",)
    assert anon_3.runs_broke == 1
    [record] = [e for e in report.executions if e.submission == "anon_3" and e.run == 1]
    assert record.status is AutograderRunStatus.TIMED_OUT
    assert record.scores == ()


def test_a_crashed_run_counts_the_same_way(tmp_path):
    def script(name, index):
        return crashed("Exited with status 3: boom") if name == "anon_1" else completed(FULL)

    report = CheckStabilityUseCase(FakeAutograderRunner(script)).execute(_request(tmp_path))

    [anon_1] = [s for s in report.submissions if s.name == "anon_1"]
    assert anon_1.runs_crashed == 4
    assert anon_1.errors == ("Exited with status 3: boom",)
    adds = _test(report, "Adds two numbers")
    assert adds.state is StabilityState.BROKE
    assert (adds.runs_agreed, adds.runs_total) == (8, 12)
    [entry] = adds.affected
    assert entry.runs_agreed == 0
    assert entry.usual is None


def test_progress_reports_the_run_and_the_submission(tmp_path):
    seen = []
    runner = FakeAutograderRunner(default=completed(FULL))

    CheckStabilityUseCase(runner).execute(_request(tmp_path, runs=2), on_progress=seen.append)

    assert [p.text for p in seen] == [
        "Run 1 of 2 1 of 6",
        "Run 1 of 2 2 of 6",
        "Run 1 of 2 3 of 6",
        "Run 2 of 2 4 of 6",
        "Run 2 of 2 5 of 6",
        "Run 2 of 2 6 of 6",
    ]
    assert {p.item for p in seen} == {"anon_1", "anon_2", "anon_3"}


def test_cancel_keeps_the_finished_runs_and_flags_the_report(tmp_path):
    done = []

    def cancelled() -> bool:
        return len(done) >= 6

    runner = FakeAutograderRunner(default=completed(FULL))

    report = CheckStabilityUseCase(runner).execute(
        _request(tmp_path, runs=5), on_progress=done.append, is_cancelled=cancelled
    )

    assert report.cancelled
    assert report.runs_requested == 5
    assert report.runs_completed == 2
    assert report.executions_total == 6
    assert len(runner.calls) == 6
    for test in report.tests:
        assert (test.runs_agreed, test.runs_total) == (6, 6)


def test_cancel_mid_run_drops_the_unfinished_run(tmp_path):
    # The check is asked before each run and before each submission in it: four
    # times for run 1, so the seventh ask lands after run 2 has scheduled anon_1.
    asks = []

    def cancelled() -> bool:
        asks.append(True)
        return len(asks) >= 7

    runner = FakeAutograderRunner(default=completed(FULL))

    report = CheckStabilityUseCase(runner).execute(
        _request(tmp_path, runs=5), is_cancelled=cancelled
    )

    assert report.cancelled
    assert report.runs_completed == 1
    assert report.executions_total == 3
    # anon_1's second run was already in flight; it finished and was then dropped.
    assert len(runner.calls) == 4


def test_criteria_come_from_the_proxy_mapping(tmp_path):
    def script(name, index):
        return completed(ADDS_FAILED) if name == "anon_2" and index == 1 else completed(FULL)

    report = CheckStabilityUseCase(FakeAutograderRunner(script)).execute(
        _request(tmp_path, mapping=MAPPING)
    )

    assert report.mapping_name == "test_m1"
    adding, printing = report.criteria
    assert adding.name == "adding"
    assert adding.state is StabilityState.CHANGED
    assert adding.built_from == ("Adds two numbers",)
    assert (adding.runs_agreed, adding.runs_total) == (11, 12)
    [entry] = adding.affected
    assert entry.results == (
        ResultSeen(score=2.0, max_score=2.0, runs=(1, 3, 4)),
        ResultSeen(score=0.0, max_score=2.0, runs=(2,)),
    )
    assert printing.state is StabilityState.PASS
    assert printing.built_from == ("Prints the total",)


def test_without_a_mapping_there_are_no_criteria(tmp_path):
    report = CheckStabilityUseCase(FakeAutograderRunner(default=completed(FULL))).execute(
        _request(tmp_path)
    )

    assert report.criteria == ()
    assert report.mapping_name is None


def test_a_mapping_the_autograder_does_not_cover_gives_no_points(tmp_path):
    only_adds = {"Adds two numbers": (2.0, 2.0)}

    report = CheckStabilityUseCase(FakeAutograderRunner(default=completed(only_adds))).execute(
        _request(tmp_path, runs=2, mapping=MAPPING)
    )

    adding, printing = report.criteria
    assert adding.state is StabilityState.BROKE
    assert printing.state is StabilityState.BROKE
    assert adding.runs_agreed == 0
    assert _test(report, "Adds two numbers").state is StabilityState.PASS


def test_a_runner_that_raises_is_recorded_as_crashed(tmp_path):
    class ExplodingRunner(FakeAutograderRunner):
        def run(self, submission_dir, autograder_dir, timeout_seconds=None):
            if Path(submission_dir).name == "anon_2":
                raise RuntimeError("worker died")
            return super().run(submission_dir, autograder_dir, timeout_seconds)

    report = CheckStabilityUseCase(ExplodingRunner(default=completed(FULL))).execute(
        _request(tmp_path, runs=1)
    )

    [anon_2] = [s for s in report.submissions if s.name == "anon_2"]
    assert anon_2.runs_crashed == 1
    assert anon_2.errors == ("RuntimeError: worker died",)


def test_executions_pass_the_timeout_and_run_in_parallel(tmp_path):
    runner = FakeAutograderRunner(default=completed(FULL))

    CheckStabilityUseCase(runner).execute(
        _request(tmp_path, runs=1, workers=3, timeout_seconds=300.0)
    )

    assert {c.timeout_seconds for c in runner.calls} == {300.0}
    assert sorted(c.submission_dir.name for c in runner.calls) == ["anon_1", "anon_2", "anon_3"]


def test_a_check_without_submissions_is_refused(tmp_path):
    with pytest.raises(NoSubmissionsError):
        CheckStabilityUseCase(FakeAutograderRunner()).execute(
            _request(tmp_path, submission_dirs=())
        )


@pytest.mark.parametrize("field, value", [("runs", 0), ("workers", 0)])
def test_the_request_rejects_impossible_counts(tmp_path, field, value):
    with pytest.raises(ValueError):
        _request(tmp_path, **{field: value})
