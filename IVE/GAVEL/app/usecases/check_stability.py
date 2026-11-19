"""Runs one autograder on every submission many times and reports what changed.

Executions go run by run: every submission is graded once, then the next
run starts, so a cancelled check still has whole runs to compare and the
progress reads "Run 4 of 20". A cancel stops new executions from being
scheduled, lets the ones in flight finish, and drops the unfinished run.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from GAVEL.app.dtos.autograder_run import AutograderRunOutcome, AutograderRunStatus
from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter
from GAVEL.app.dtos.proxy_grade_mapping import ProxyGradeMapping
from GAVEL.app.dtos.stability import (
    ExecutionRecord,
    ItemStability,
    ResultSeen,
    StabilityReport,
    StabilityState,
    SubmissionItemStability,
    SubmissionStability,
    severity,
    worst,
)
from GAVEL.app.ports.autograder_runner import AutograderRunner
from GAVEL.app.progress import ProgressCallback, report
from GAVEL.app.usecases.proxy_grade.compute_proxy_grade import (
    MissingTestResultsError,
    compute_proxy_grade,
)

log = logging.getLogger(__name__)

# Answers "should we stop?"; checked before every execution is scheduled.
CancelCheck = Callable[[], bool]


@dataclass(frozen=True)
class CheckStabilityRequest:
    course: str
    module_number: int
    autograder: str
    autograder_dir: Path
    # One folder per submission; each is graded ``runs`` times.
    submission_dirs: tuple[Path, ...]
    runs: int
    workers: int = 1
    timeout_seconds: float | None = None
    # Turns test results into rubric points; None leaves the criteria out.
    mapping: ProxyGradeMapping | None = None

    def __post_init__(self) -> None:
        if self.runs < 1:
            raise ValueError("A stability check needs at least one run.")
        if self.workers < 1:
            raise ValueError("A stability check needs at least one worker.")


class NoSubmissionsError(ValueError):
    pass


class CheckStabilityUseCase:
    def __init__(
        self,
        runner: AutograderRunner,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._runner = runner
        self._clock = clock

    def execute(
        self,
        request: CheckStabilityRequest,
        on_progress: ProgressCallback | None = None,
        is_cancelled: CancelCheck | None = None,
    ) -> StabilityReport:
        cancelled_check = is_cancelled or (lambda: False)
        submission_dirs = sorted((Path(p) for p in request.submission_dirs), key=lambda p: p.name)
        if not submission_dirs:
            raise NoSubmissionsError("A stability check needs at least one submission.")

        started = self._clock()
        total = request.runs * len(submission_dirs)
        done = 0
        executions: list[ExecutionRecord] = []
        runs_completed = 0
        cancelled = False
        log.info(
            "Stability check: %s on %d submissions, %d runs, %d workers",
            request.autograder,
            len(submission_dirs),
            request.runs,
            request.workers,
        )

        with ThreadPoolExecutor(max_workers=request.workers) as pool:
            for run in range(1, request.runs + 1):
                if cancelled_check():
                    cancelled = True
                    break
                label = f"Run {run} of {request.runs}"
                futures = {}
                for folder in submission_dirs:
                    if cancelled_check():
                        cancelled = True
                        break
                    future = pool.submit(
                        self._run_one, folder, request.autograder_dir, request.timeout_seconds
                    )
                    futures[future] = folder

                records = []
                for future in as_completed(futures):
                    folder = futures[future]
                    records.append(_record(folder.name, run, future.result()))
                    done += 1
                    report(on_progress, label, done, total, folder.name)

                if cancelled or len(records) < len(submission_dirs):
                    cancelled = True
                    log.info("Stability check cancelled during run %d; keeping %d", run, run - 1)
                    break
                executions.extend(sorted(records, key=lambda r: r.submission))
                runs_completed += 1

        finished = self._clock()
        return build_report(
            request,
            submissions=tuple(p.name for p in submission_dirs),
            executions=tuple(executions),
            runs_completed=runs_completed,
            cancelled=cancelled,
            started_at=started,
            finished_at=finished,
        )

    def _run_one(
        self, folder: Path, autograder_dir: Path, timeout_seconds: float | None
    ) -> AutograderRunOutcome:
        try:
            return self._runner.run(folder, autograder_dir, timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - a runner bug must not sink the whole check
            log.exception("Runner failed on %s", folder.name)
            return AutograderRunOutcome(
                status=AutograderRunStatus.CRASHED,
                duration_seconds=0.0,
                error=f"{type(exc).__name__}: {exc}",
            )


def _record(submission: str, run: int, outcome: AutograderRunOutcome) -> ExecutionRecord:
    return ExecutionRecord(
        submission=submission,
        run=run,
        status=outcome.status,
        duration_seconds=outcome.duration_seconds,
        scores=tuple(outcome.tests) if outcome.completed else (),
        error=outcome.error,
        output_tail="" if outcome.completed else outcome.output_tail,
    )


# ----- rolling executions up into the report -------------------------------------------

# One item's result in one execution: (score, max_score, output), or None for no result.
_Value = tuple[float, float | None, str | None] | None


def build_report(
    request: CheckStabilityRequest,
    submissions: tuple[str, ...],
    executions: tuple[ExecutionRecord, ...],
    runs_completed: int,
    cancelled: bool,
    started_at: datetime,
    finished_at: datetime,
) -> StabilityReport:
    by_submission: dict[str, list[ExecutionRecord]] = {name: [] for name in submissions}
    for execution in executions:
        by_submission[execution.submission].append(execution)
    for records in by_submission.values():
        records.sort(key=lambda r: r.run)

    test_names = _test_names(executions)
    tests = tuple(
        _item(name, by_submission, lambda e, n=name: _test_value(e, n)) for name in test_names
    )

    criteria: tuple[ItemStability, ...] = ()
    mapping = request.mapping
    if mapping is not None:
        points = {
            (e.submission, e.run): _criterion_points(e, mapping) for e in executions if e.completed
        }
        criteria = tuple(
            _item(
                criterion.name,
                by_submission,
                lambda e, i=index: _criterion_value(points.get((e.submission, e.run)), i, mapping),
                built_from=_criterion_tests(mapping, index),
            )
            for index, criterion in enumerate(mapping.criteria)
        )

    return StabilityReport(
        course=request.course,
        module_number=request.module_number,
        autograder=request.autograder,
        runs_requested=request.runs,
        runs_completed=runs_completed,
        cancelled=cancelled,
        workers=request.workers,
        timeout_seconds=request.timeout_seconds,
        started_at=started_at.isoformat(timespec="seconds"),
        finished_at=finished_at.isoformat(timespec="seconds"),
        submissions=tuple(_submission(name, by_submission[name]) for name in submissions),
        tests=tests,
        criteria=criteria,
        mapping_name=mapping.name if mapping is not None else None,
        executions=executions,
    )


def _test_names(executions: tuple[ExecutionRecord, ...]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for execution in executions:
        for score in execution.scores:
            seen.setdefault(score.name, None)
    return tuple(seen)


def _test_value(execution: ExecutionRecord, name: str) -> _Value:
    if not execution.completed:
        return None
    for score in execution.scores:
        if score.name == name:
            return (score.score, score.max_score, score.output)
    return None


def _criterion_points(
    execution: ExecutionRecord, mapping: ProxyGradeMapping
) -> tuple[float, ...] | None:
    submission = GradescopeSubmission(
        submission_key=execution.submission,
        submitter=GradescopeSubmitter(sid="", email="", name=""),
        created_at=datetime.min,
        tests=list(execution.scores),
    )
    try:
        return compute_proxy_grade(submission, mapping).criterion_scores
    except MissingTestResultsError:
        # The autograder's test names do not cover the mapping; no points can be derived.
        return None


def _criterion_value(
    points: tuple[float, ...] | None, index: int, mapping: ProxyGradeMapping
) -> _Value:
    if points is None:
        return None
    top = max(tier.points for tier in mapping.criteria[index].tiers)
    return (points[index], top, None)


def _criterion_tests(mapping: ProxyGradeMapping, index: int) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for tier in mapping.criteria[index].tiers:
        for name in (*tier.all_of, *tier.any_of):
            seen.setdefault(name, None)
    return tuple(seen)


def _item(
    name: str,
    by_submission: dict[str, list[ExecutionRecord]],
    value_of: Callable[[ExecutionRecord], _Value],
    built_from: tuple[str, ...] = (),
) -> ItemStability:
    entries = [
        _submission_item(submission, [(e.run, value_of(e)) for e in records])
        for submission, records in by_submission.items()
        if records
    ]
    # Worst first: Broke before Changed, then the lowest agreement, then by name.
    affected = sorted(
        (entry for entry in entries if entry.state is not StabilityState.PASS),
        key=lambda entry: (
            -severity(entry.state),
            entry.runs_agreed / entry.runs_total,
            entry.submission,
        ),
    )
    return ItemStability(
        name=name,
        state=worst(tuple(entry.state for entry in entries)),
        runs_agreed=sum(entry.runs_agreed for entry in entries),
        runs_total=sum(entry.runs_total for entry in entries),
        submissions_total=len(entries),
        affected=tuple(affected),
        built_from=built_from,
    )


def _submission_item(submission: str, values: list[tuple[int, _Value]]) -> SubmissionItemStability:
    groups: dict[tuple[float | None, float | None], list[int]] = {}
    outputs: dict[tuple[float | None, float | None], str | None] = {}
    for run, value in values:
        key = (None, None) if value is None else (value[0], value[1])
        groups.setdefault(key, []).append(run)
        if value is not None:
            outputs.setdefault(key, value[2])

    results = [
        ResultSeen(score=key[0], max_score=key[1], runs=tuple(runs), output=outputs.get(key))
        for key, runs in groups.items()
    ]
    # The usual result is the one most runs gave; the earliest run breaks ties.
    # Runs with no result always sort last.
    results.sort(key=lambda r: (r.score is None, -len(r.runs), r.runs[0]))

    with_result = [r for r in results if r.score is not None]
    without_result = [r for r in results if r.score is None]
    if without_result:
        state = StabilityState.BROKE
    elif len(with_result) > 1:
        state = StabilityState.CHANGED
    else:
        state = StabilityState.PASS
    return SubmissionItemStability(
        submission=submission,
        state=state,
        runs_agreed=len(with_result[0].runs) if with_result else 0,
        runs_total=len(values),
        results=tuple(results),
    )


def _submission(name: str, records: list[ExecutionRecord]) -> SubmissionStability:
    errors: dict[str, None] = {}
    for record in records:
        if record.error:
            errors.setdefault(record.error, None)
    return SubmissionStability(
        name=name,
        runs_completed=sum(1 for r in records if r.status is AutograderRunStatus.COMPLETED),
        runs_timed_out=sum(1 for r in records if r.status is AutograderRunStatus.TIMED_OUT),
        runs_crashed=sum(1 for r in records if r.status is AutograderRunStatus.CRASHED),
        errors=tuple(errors),
    )
