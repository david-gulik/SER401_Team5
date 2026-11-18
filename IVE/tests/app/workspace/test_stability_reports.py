from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier
from GAVEL.app.dtos.stability import StabilityState
from GAVEL.app.usecases.check_stability import CheckStabilityRequest, CheckStabilityUseCase
from GAVEL.app.workspace.layout import Workspace
from GAVEL.app.workspace.stability_reports import (
    StabilityReportStore,
    report_from_json,
    report_to_json,
)
from tests.fakes.autograder_runner import FakeAutograderRunner, completed, timed_out

MAPPING = ProxyGradeMapping(
    name="test_m1", criteria=(Criterion("adding", (Tier(2.0, all_of=("Adds",)),)),)
)


def _report(tmp_path: Path, started: datetime, flaky: bool = True):
    folder = tmp_path / "extracted"
    folder.mkdir(exist_ok=True)
    for name in ("anon_1", "anon_2"):
        (folder / name).mkdir(exist_ok=True)

    def script(name, index):
        if flaky and name == "anon_2" and index == 1:
            return timed_out(5.0)
        if flaky and name == "anon_2" and index == 2:
            return completed({"Adds": (0.0, 2.0)}, output_tail="x")
        return completed({"Adds": (2.0, 2.0)})

    times = iter([started, started.replace(minute=started.minute + 5)])
    request = CheckStabilityRequest(
        course="ser334_25fc_82931",
        module_number=9,
        autograder="ser334_m9_grader.zip",
        autograder_dir=tmp_path / "grader",
        submissions_dir=folder,
        runs=3,
        workers=2,
        timeout_seconds=5.0,
        mapping=MAPPING,
    )
    return CheckStabilityUseCase(FakeAutograderRunner(script), lambda: next(times)).execute(request)


@pytest.fixture
def store(tmp_path: Path) -> StabilityReportStore:
    return StabilityReportStore(Workspace(tmp_path / "workspace"))


def test_a_report_round_trips_through_json(tmp_path):
    report = _report(tmp_path, datetime(2026, 11, 16, 14, 0, 0))

    restored = report_from_json(report_to_json(report))

    assert restored == report
    assert restored.verdict is StabilityState.BROKE
    assert restored.criteria[0].built_from == ("Adds",)


def test_json_carries_a_schema_version_and_plain_values(tmp_path):
    report = _report(tmp_path, datetime(2026, 11, 16, 14, 0, 0))

    data = json.loads(report_to_json(report))

    assert data["schema_version"] == 1
    assert data["tests"][0]["state"] == "broke"
    assert data["executions"][0]["status"] == "completed"


def test_an_unknown_schema_version_is_refused():
    with pytest.raises(ValueError):
        report_from_json(json.dumps({"schema_version": 99}))


def test_save_puts_the_report_under_the_runs_folder(store, tmp_path):
    report = _report(tmp_path, datetime(2026, 11, 16, 14, 0, 0))

    path = store.save(report)

    expected = (
        tmp_path
        / "workspace"
        / "runs"
        / "ser334_25fc_82931"
        / "m9"
        / "ser334_m9_grader.zip"
        / "2026-11-16T14-00-00.json"
    )
    assert path == expected
    assert path.is_file()
    assert store.load(path) == report


def test_list_gives_newest_first_with_a_summary(store, tmp_path):
    older = _report(tmp_path, datetime(2026, 11, 1, 9, 12, 0), flaky=False)
    newer = _report(tmp_path, datetime(2026, 11, 16, 14, 0, 0))
    store.save(older)
    newer_path = store.save(newer)

    summaries = store.list("ser334_25fc_82931", 9, "ser334_m9_grader.zip")

    assert [s.started_at for s in summaries] == ["2026-11-16T14:00:00", "2026-11-01T09:12:00"]
    assert summaries[0].path == newer_path
    assert summaries[0].verdict is StabilityState.BROKE
    assert (summaries[0].runs_completed, summaries[0].runs_requested) == (3, 3)
    assert summaries[0].tests_broke == 1
    assert summaries[1].verdict is StabilityState.PASS
    assert not summaries[1].cancelled


def test_list_is_empty_for_an_assignment_never_checked(store):
    assert store.list("ser334_25fc_82931", 3, "other.zip") == ()
