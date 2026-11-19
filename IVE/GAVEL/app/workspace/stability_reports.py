"""Saved stability reports: ``runs/<course>/m<module>/<autograder>/<started>.json``.

One file per check, named by its start time, so earlier checks of the same
assignment and autograder sit side by side and can be reopened.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.autograder_run import AutograderRunStatus
from GAVEL.app.dtos.gradescope import GradescopeTestScore
from GAVEL.app.dtos.stability import (
    ExecutionRecord,
    ItemStability,
    ResultSeen,
    StabilityReport,
    StabilityState,
    SubmissionItemStability,
    SubmissionStability,
)
from GAVEL.app.workspace.layout import Workspace

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ReportSummary:
    """Enough about a saved report to list it without showing its tree."""

    path: Path
    started_at: str
    runs_requested: int
    runs_completed: int
    cancelled: bool
    verdict: StabilityState
    tests_changed: int
    tests_broke: int


class StabilityReportStore:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def folder(self, course: str, module_number: int, autograder: str) -> Path:
        return self._workspace.runs_dir / course / f"m{module_number}" / autograder

    def save(self, report: StabilityReport) -> Path:
        folder = self.folder(report.course, report.module_number, report.autograder)
        folder.mkdir(parents=True, exist_ok=True)
        # Colons are not allowed in Windows file names.
        path = folder / (report.started_at.replace(":", "-") + ".json")
        path.write_text(report_to_json(report), encoding="utf-8")
        return path

    def list(self, course: str, module_number: int, autograder: str) -> tuple[ReportSummary, ...]:
        """Saved reports for one assignment and autograder, newest first."""
        folder = self.folder(course, module_number, autograder)
        if not folder.is_dir():
            return ()
        summaries = []
        for path in folder.glob("*.json"):
            report = self.load(path)
            summaries.append(
                ReportSummary(
                    path=path,
                    started_at=report.started_at,
                    runs_requested=report.runs_requested,
                    runs_completed=report.runs_completed,
                    cancelled=report.cancelled,
                    verdict=report.verdict,
                    tests_changed=len(report.tests_in(StabilityState.CHANGED)),
                    tests_broke=len(report.tests_in(StabilityState.BROKE)),
                )
            )
        summaries.sort(key=lambda s: s.started_at, reverse=True)
        return tuple(summaries)

    def load(self, path: Path) -> StabilityReport:
        return report_from_json(Path(path).read_text(encoding="utf-8"))


# ----- JSON shape -------------------------------------------------------------------------


def report_to_json(report: StabilityReport) -> str:
    data = {
        "schema_version": SCHEMA_VERSION,
        "course": report.course,
        "module_number": report.module_number,
        "autograder": report.autograder,
        "runs_requested": report.runs_requested,
        "runs_completed": report.runs_completed,
        "cancelled": report.cancelled,
        "workers": report.workers,
        "timeout_seconds": report.timeout_seconds,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "mapping_name": report.mapping_name,
        "submissions": [
            {
                "name": s.name,
                "runs_completed": s.runs_completed,
                "runs_timed_out": s.runs_timed_out,
                "runs_crashed": s.runs_crashed,
                "errors": list(s.errors),
            }
            for s in report.submissions
        ],
        "tests": [_item_to_dict(t) for t in report.tests],
        "criteria": [_item_to_dict(c) for c in report.criteria],
        "executions": [
            {
                "submission": e.submission,
                "run": e.run,
                "status": e.status.value,
                "duration_seconds": e.duration_seconds,
                "scores": [
                    {
                        "name": t.name,
                        "score": t.score,
                        "max_score": t.max_score,
                        "number": t.number,
                        "output": t.output,
                    }
                    for t in e.scores
                ],
                "error": e.error,
                "output_tail": e.output_tail,
            }
            for e in report.executions
        ],
    }
    return json.dumps(data, indent=2)


def report_from_json(text: str) -> StabilityReport:
    data = json.loads(text)
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"Unsupported stability report schema version {version!r}")
    return StabilityReport(
        course=data["course"],
        module_number=int(data["module_number"]),
        autograder=data["autograder"],
        runs_requested=int(data["runs_requested"]),
        runs_completed=int(data["runs_completed"]),
        cancelled=bool(data["cancelled"]),
        workers=int(data["workers"]),
        timeout_seconds=data["timeout_seconds"],
        started_at=data["started_at"],
        finished_at=data["finished_at"],
        submissions=tuple(
            SubmissionStability(
                name=s["name"],
                runs_completed=int(s["runs_completed"]),
                runs_timed_out=int(s["runs_timed_out"]),
                runs_crashed=int(s["runs_crashed"]),
                errors=tuple(s["errors"]),
            )
            for s in data["submissions"]
        ),
        tests=tuple(_item_from_dict(t) for t in data["tests"]),
        criteria=tuple(_item_from_dict(c) for c in data["criteria"]),
        mapping_name=data["mapping_name"],
        executions=tuple(
            ExecutionRecord(
                submission=e["submission"],
                run=int(e["run"]),
                status=AutograderRunStatus(e["status"]),
                duration_seconds=float(e["duration_seconds"]),
                scores=tuple(
                    GradescopeTestScore(
                        name=t["name"],
                        score=float(t["score"]),
                        max_score=t["max_score"],
                        number=t["number"],
                        output=t["output"],
                    )
                    for t in e["scores"]
                ),
                error=e["error"],
                output_tail=e["output_tail"],
            )
            for e in data["executions"]
        ),
    )


def _item_to_dict(item: ItemStability) -> dict:
    return {
        "name": item.name,
        "state": item.state.value,
        "runs_agreed": item.runs_agreed,
        "runs_total": item.runs_total,
        "submissions_total": item.submissions_total,
        "built_from": list(item.built_from),
        "affected": [
            {
                "submission": a.submission,
                "state": a.state.value,
                "runs_agreed": a.runs_agreed,
                "runs_total": a.runs_total,
                "results": [
                    {
                        "score": r.score,
                        "max_score": r.max_score,
                        "runs": list(r.runs),
                        "output": r.output,
                    }
                    for r in a.results
                ],
            }
            for a in item.affected
        ],
    }


def _item_from_dict(data: dict) -> ItemStability:
    return ItemStability(
        name=data["name"],
        state=StabilityState(data["state"]),
        runs_agreed=int(data["runs_agreed"]),
        runs_total=int(data["runs_total"]),
        submissions_total=int(data["submissions_total"]),
        built_from=tuple(data["built_from"]),
        affected=tuple(
            SubmissionItemStability(
                submission=a["submission"],
                state=StabilityState(a["state"]),
                runs_agreed=int(a["runs_agreed"]),
                runs_total=int(a["runs_total"]),
                results=tuple(
                    ResultSeen(
                        score=r["score"],
                        max_score=r["max_score"],
                        runs=tuple(int(n) for n in r["runs"]),
                        output=r["output"],
                    )
                    for r in a["results"]
                ),
            )
            for a in data["affected"]
        ),
    )
