from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.stability import StabilityState
from GAVEL.app.workspace.stability_reports import StabilityReportStore
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.core.background import run_now
from GAVEL.pages.stability_check.viewmodel import (
    DEFAULT_RUNS,
    DEFAULT_TIMEOUT_MINUTES,
    Phase,
    StabilityCheckViewModel,
)
from tests.fakes.autograder_runner import FakeAutograderRunner, completed, timed_out


def _viewmodel(workspace, runner=None, workers=4) -> StabilityCheckViewModel:
    return StabilityCheckViewModel(
        dataset_readers=build_dataset_readers(),
        workspace=workspace,
        runner=runner or FakeAutograderRunner(default=completed({"Adds": (2.0, 2.0)})),
        background=run_now,
        workers=workers,
    )


@pytest.fixture
def ready(qapp, workspace, course) -> StabilityCheckViewModel:
    vm = _viewmodel(workspace)
    vm.select_course(course)
    vm.select_module(9)
    vm.select_autograder("folder_grader")
    return vm


def test_starts_with_the_defaults_and_nothing_picked(qapp, workspace):
    vm = _viewmodel(workspace)

    assert vm.state.phase is Phase.SET_UP
    assert vm.state.runs == DEFAULT_RUNS
    assert vm.state.timeout_minutes == DEFAULT_TIMEOUT_MINUTES
    assert vm.state.workers == 4
    assert vm.state.missing == "Choose a course"
    assert vm.state.estimate == ""


def test_a_course_lists_the_modules_that_have_submissions(qapp, workspace, course):
    vm = _viewmodel(workspace)

    vm.select_course(course)

    assert [(m.module_number, m.submissions) for m in vm.state.modules] == [(3, 1), (9, 3)]
    assert vm.state.modules[1].label == "Module 9"
    assert vm.state.course_error is None
    assert vm.state.missing == "Choose an assignment"


def test_a_course_without_submissions_says_so(qapp, tmp_path):
    from GAVEL.app.workspace.layout import Workspace

    root = tmp_path / "empty"
    (root / "courses" / "ser222_25sc_12345").mkdir(parents=True)
    workspace = Workspace(root)
    [course] = workspace.list_courses()
    vm = _viewmodel(workspace)

    vm.select_course(course)

    assert vm.state.modules == ()
    assert vm.state.course_error == "No anonymized submissions in this course. Sanitize it first."


def test_a_module_lists_its_folders_and_the_course_zips(qapp, workspace, course):
    vm = _viewmodel(workspace)
    vm.select_course(course)

    vm.select_module(9)

    assert [(a.name, a.is_zip) for a in vm.state.autograders] == [
        ("folder_grader", False),
        ("zipped_grader", True),
    ]
    assert vm.state.missing == "Choose an autograder"

    vm.select_module(3)

    assert [a.name for a in vm.state.autograders] == ["zipped_grader"]


def test_picking_everything_enables_the_run_and_the_estimate(ready):
    assert ready.state.missing is None
    assert ready.state.executions == 30
    assert ready.state.estimate == (
        "3 submissions × 10 runs = 30 executions · no earlier check to estimate the time from"
    )
    assert ready.state.summary == (
        "Module 9 · folder_grader · 3 submissions × 10 runs · 4 workers · 5 min timeout"
    )


def test_settings_are_clamped(ready):
    ready.set_runs(1)
    assert ready.state.runs == 2
    ready.set_runs(500)
    assert ready.state.runs == 100
    ready.set_workers(0)
    assert ready.state.workers == 1
    ready.set_timeout_minutes(0)
    assert ready.state.timeout_minutes == 1


def test_a_check_runs_saves_and_reports(ready, workspace):
    ready.set_runs(2)
    phases = []
    ready.state_changed.connect(lambda s: phases.append(s.phase))

    ready.start()

    assert ready.state.phase is Phase.DONE
    assert Phase.RUNNING in phases
    report = ready.state.report
    assert report is not None
    assert report.verdict is StabilityState.PASS
    assert report.runs_completed == 2
    assert [s.name for s in report.submissions] == ["anon_1093", "anon_4821", "anon_7742"]
    assert report.workers == 4
    assert report.timeout_seconds == 300.0
    assert report.mapping_name == "ser334_m9"
    assert ready.state.saved_to is not None
    assert ready.state.saved_to.is_file()
    assert (
        ready.state.saved_to.parent
        == workspace.runs_dir / "ser334_25fc_82931" / "m9" / "folder_grader"
    )
    assert ready.state.progress is not None
    assert ready.state.progress.text == "Run 2 of 2 6 of 6"
    assert len(ready.state.previous) == 1


def test_the_next_estimate_uses_the_last_check(ready):
    ready.set_runs(2)
    ready.start()

    ready.select_autograder("folder_grader")

    assert ready.state.estimate.startswith("3 submissions × 2 runs = 6 executions · about 1 min")


def test_a_zip_is_extracted_once_and_reused(qapp, workspace, course):
    runner = FakeAutograderRunner(default=completed({"Adds": (2.0, 2.0)}))
    vm = _viewmodel(workspace, runner)
    vm.select_course(course)
    vm.select_module(9)
    vm.select_autograder("zipped_grader")
    vm.set_runs(2)

    vm.start()

    extracted = workspace.course_autograders_dir(course.key) / "m9" / "zipped_grader"
    assert (extracted / "config.json").is_file()
    assert (extracted / "main.py").is_file()
    assert {c.autograder_dir for c in runner.calls} == {extracted}

    vm.select_module(9)
    # Listed as a folder now, and first: the extraction is newer than folder_grader.
    assert [(a.name, a.is_zip) for a in vm.state.autograders] == [
        ("zipped_grader", False),
        ("folder_grader", False),
    ]


def test_a_broken_run_is_reported_not_raised(qapp, workspace, course):
    def script(name, index):
        return timed_out(300.0) if name == "anon_4821" else completed({"Adds": (2.0, 2.0)})

    vm = _viewmodel(workspace, FakeAutograderRunner(script))
    vm.select_course(course)
    vm.select_module(9)
    vm.select_autograder("folder_grader")
    vm.set_runs(2)

    vm.start()

    assert vm.state.phase is Phase.DONE
    assert vm.state.report is not None
    assert vm.state.report.verdict is StabilityState.BROKE


def test_a_failure_before_the_check_starts_is_shown(qapp, workspace, course, monkeypatch):
    import GAVEL.pages.stability_check.viewmodel as module

    def broken_extract(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(module, "ensure_extracted", broken_extract)
    vm = _viewmodel(workspace)
    vm.select_course(course)
    vm.select_module(9)
    vm.select_autograder("folder_grader")

    vm.start()

    assert vm.state.phase is Phase.FAILED
    assert vm.state.error == "OSError: disk full"


def test_cancel_outside_a_run_does_nothing(ready):
    ready.cancel()

    assert not ready.state.cancel_requested
    assert ready.state.phase is Phase.SET_UP


def test_a_course_change_during_a_run_waits_for_the_run(qapp, workspace, course, tmp_path):
    from GAVEL.app.workspace.layout import Workspace

    other_root = tmp_path / "other"
    (other_root / "courses" / "ser222_25sc_12345").mkdir(parents=True)
    [other] = Workspace(other_root).list_courses()

    class SwitchingRunner(FakeAutograderRunner):
        def run(self, submission_dir, autograder_dir, timeout_seconds=None):
            vm.select_course(other)  # arrives while the check is running
            return super().run(submission_dir, autograder_dir, timeout_seconds)

    vm = _viewmodel(workspace, SwitchingRunner(default=completed({"Adds": (2.0, 2.0)})))
    vm.select_course(course)
    vm.select_module(9)
    vm.select_autograder("folder_grader")
    vm.set_runs(2)

    vm.start()

    assert vm.state.course == other
    assert vm.state.phase is Phase.SET_UP
    assert vm.state.report is None


def test_the_autograder_of_the_latest_check_starts_picked(ready, workspace, course):
    ready.set_runs(2)
    ready.start()
    ready.select_autograder("zipped_grader")
    ready.start()

    ready.select_module(3)

    assert ready.state.autograder is None, "never checked, so nothing is picked"

    ready.select_module(9)

    assert ready.state.autograder is not None
    assert ready.state.autograder.name == "zipped_grader"
    assert len(ready.state.previous) == 1


def test_previous_checks_are_listed_for_the_picked_autograder(ready, workspace, course):
    store = StabilityReportStore(workspace)
    assert store.list(course.key.folder_name, 9, "folder_grader") == ()
    ready.set_runs(2)
    ready.start()
    ready.start()

    ready.select_autograder("folder_grader")

    assert len(ready.state.previous) == 2
    assert all(isinstance(p.path, Path) for p in ready.state.previous)


def test_a_saved_report_can_be_reopened(ready):
    ready.set_runs(2)
    ready.start()
    saved = ready.state.saved_to
    assert saved is not None
    ready.edit_settings()
    assert ready.state.phase is Phase.SET_UP
    assert ready.state.report is not None

    ready.select_course(None)
    assert ready.state.report is None

    ready.open_report(saved)

    assert ready.state.phase is Phase.DONE
    assert ready.state.saved_to == saved
    assert ready.state.report is not None
    assert ready.state.report.runs_completed == 2


def test_a_previous_check_can_be_deleted_but_not_the_one_on_screen(ready):
    ready.set_runs(2)
    ready.start()
    first = ready.state.saved_to
    ready.start()
    second = ready.state.saved_to
    assert first is not None and second is not None and first != second
    assert len(ready.state.previous) == 2

    ready.delete_report(second)

    assert second.exists(), "the report on screen stays"
    assert len(ready.state.previous) == 2

    ready.delete_report(first)

    assert not first.exists()
    assert [p.path for p in ready.state.previous] == [second]
    assert ready.state.report is not None and ready.state.phase is Phase.DONE


def test_opening_a_bad_file_is_reported(ready, tmp_path):
    bad = tmp_path / "not-a-report.json"
    bad.write_text("{}", encoding="utf-8")

    ready.open_report(bad)

    assert ready.state.phase is Phase.FAILED
    assert ready.state.error is not None
    assert ready.state.error.startswith("Could not open not-a-report.json")


def test_submission_folder_follows_the_shown_report(ready, workspace, course):
    assert ready.submission_folder("anon_4821") is None  # no report yet
    ready.set_runs(2)
    ready.start()

    folder = ready.submission_folder("anon_4821")

    assert folder is not None
    assert folder.name == "anon_4821"
    assert folder.parent.name == "m9"
    assert ready.submission_folder("missing") is None
