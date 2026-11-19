from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QHeaderView

from GAVEL.app.dtos.autograder_run import AutograderRunOutcome, AutograderRunStatus
from GAVEL.app.dtos.stability import StabilityState
from GAVEL.app.usecases.check_stability import CheckStabilityRequest, CheckStabilityUseCase
from GAVEL.pages.stability_check.results_view import RUNS_SHOWN_AT_FIRST, ResultsView, SortOrder
from GAVEL.pages.stability_check.run_output_dialog import run_output_text
from tests.fakes.autograder_runner import FakeAutograderRunner, completed, timed_out

TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "main.py", line 12, in <module>\n'
    "    grade()\n"
    "ZeroDivisionError: division by zero\n"
)

FULL = {"Adds": (2.0, 2.0), "Prints": (1.0, 1.0), "Sorts": (3.0, 3.0)}


def _report(tmp_path: Path, script, runs=6, cancelled_at=None):
    folder = tmp_path / "extracted"
    folder.mkdir(exist_ok=True)
    names = ("anon_1", "anon_2", "anon_3")
    for name in names:
        (folder / name).mkdir(exist_ok=True)
    times = iter([datetime(2026, 11, 16, 14, 2, 0), datetime(2026, 11, 16, 14, 25, 36)])
    request = CheckStabilityRequest(
        course="ser334_25fc_82931",
        module_number=9,
        autograder="ser334_m9_grader",
        autograder_dir=tmp_path / "grader",
        submission_dirs=tuple(folder / n for n in names),
        runs=runs,
    )
    done = []
    use_case = CheckStabilityUseCase(FakeAutograderRunner(script), lambda: next(times))
    return use_case.execute(
        request,
        on_progress=done.append,
        is_cancelled=(lambda: len(done) >= cancelled_at) if cancelled_at else None,
    )


def _mixed(name, index):
    """anon_2 flips Adds on even runs; anon_3 times out on run 2; Sorts flips once for anon_1."""
    if name == "anon_3" and index == 1:
        return timed_out(300.0)
    if name == "anon_2" and index % 2 == 1:
        return completed({**FULL, "Adds": (0.0, 2.0)}, output_tail="x")
    if name == "anon_1" and index == 4:
        return completed({**FULL, "Sorts": (1.0, 3.0)})
    return completed(FULL)


@pytest.fixture
def view(qapp, theme) -> ResultsView:
    return ResultsView(theme)


def _top(view: ResultsView) -> list[str]:
    return [view.tree.topLevelItem(i).text(0) for i in range(view.tree.topLevelItemCount())]


def _children(item) -> list:
    return [item.child(i) for i in range(item.childCount())]


def test_the_band_sums_up_a_mixed_report(view, tmp_path):
    report = _report(tmp_path, _mixed)

    view.set_report(report, tmp_path / "saved.json")

    assert view.verdict_badge.text() == "BROKEN"
    assert view.headline_label.text() == (
        "2 tests changed result between runs, and 1 submission timed out or crashed on some runs."
    )
    assert view.meta_label.text() == (
        "ser334_m9_grader · Module 9 · 3 submissions × 6 runs · 23 min 36 s · "
        "finished 2026-11-16 14:25:36"
    )
    assert view.tile_texts == {
        "stable": "Stable 1 tests",
        "changed": "Changed 2 tests",
        "broke": "Broke 1 submissions",
        "affected": "Affected 3 of 3 submissions",
    }
    assert "Stable&nbsp;<b>1</b>&nbsp;tests" in view.tiles_label.text()
    assert not view.banner_label.isVisibleTo(view)
    assert view.saved_label.text().endswith("saved.json")


def test_a_stable_report_reads_as_stable(view, tmp_path):
    report = _report(tmp_path, lambda name, index: completed(FULL), runs=3)

    view.set_report(report)

    assert view.verdict_badge.text() == "STABLE"
    assert view.headline_label.text() == "Every test gave the same result on every run."
    assert _top(view) == ["Stable · 3 tests · tick Show stable tests to list them"]
    assert view.tree.topLevelItem(0).childCount() == 0

    view.show_stable_check.setChecked(True)

    assert view.tree.topLevelItem(0).childCount() == 3
    assert [c.text(0) for c in _children(view.tree.topLevelItem(0))] == ["Adds", "Prints", "Sorts"]


def test_groups_come_in_a_fixed_order_with_the_worst_test_first(view, tmp_path):
    view.set_report(_report(tmp_path, _mixed))

    tops = _top(view)
    assert tops[0] == "Broke · 1 submission"
    assert tops[1] == "Changed · 2 tests"
    assert tops[2] == "Stable · 1 test · tick Show stable tests to list them"
    # The definitions sit in the tooltips and the footnote, so the rows stay short.
    assert view.tree.topLevelItem(1).toolTip(0) == (
        "Changed: the same submission scored differently on different runs."
    )
    assert view.footnote.text().startswith("Broke: the autograder timed out or crashed")

    changed = view.tree.topLevelItem(1)
    assert [c.text(0) for c in _children(changed)] == ["Adds", "Sorts"]
    adds = changed.child(0)
    assert adds.text(2) == "1 of 3"
    cell = view.tree.itemWidget(adds, 1)
    assert cell.text == "78% · 14/18"
    assert (cell.bar.agreed, cell.bar.changed, cell.bar.broke) == (14, 3, 1)


def test_sorting_reorders_within_a_group_only(view, tmp_path):
    view.set_report(_report(tmp_path, _mixed))

    view.sort_combo.setCurrentIndex(list(SortOrder).index(SortOrder.NAME))
    changed = view.tree.topLevelItem(1)
    assert [c.text(0) for c in _children(changed)] == ["Adds", "Sorts"]
    assert _top(view)[0].startswith("Broke")

    view.sort_combo.setCurrentIndex(list(SortOrder).index(SortOrder.MOST_AFFECTED))
    assert [c.text(0) for c in _children(view.tree.topLevelItem(1))] == ["Adds", "Sorts"]


def test_the_tree_goes_test_submission_result_run(view, tmp_path):
    view.set_report(_report(tmp_path, _mixed))

    adds = view.tree.topLevelItem(1).child(0)
    [anon_2] = _children(adds)
    assert anon_2.text(0) == "anon_2"
    assert anon_2.text(2) == "2/2 pts ×3 · 0/2 pts ×3"
    assert view.tree.itemWidget(anon_2, 1).text == "3/6"

    usual, differing, all_runs, folder = _children(anon_2)
    assert all_runs.text(0) == "All runs"
    assert folder.text(0) == "Open submission folder"
    assert usual.text(0) == "2/2 pts · usual result"
    assert usual.text(2) == "3 runs"
    assert differing.text(0) == "0/2 pts · differs from the usual result"
    assert [r.text(0) for r in _children(differing)] == ["Run 2", "Run 4", "Run 6"]
    assert _children(differing)[0].text(2) == "1.0 s"


def test_broken_submissions_list_their_failed_runs(view, tmp_path):
    view.set_report(_report(tmp_path, _mixed))

    broke = view.tree.topLevelItem(0)
    [anon_3] = _children(broke)
    assert anon_3.text(0) == "anon_3"
    assert anon_3.text(2) == "timed out ×1"
    assert view.tree.itemWidget(anon_3, 1).text == "5/6"
    run, folder = _children(anon_3)
    assert folder.text(0) == "Open submission folder"
    assert run.text(0) == "Run 2"
    assert run.text(2) == "timed out · Stopped after 300.0 seconds"


def test_long_run_lists_fold_behind_show_more(view, tmp_path):
    def script(name, index):
        if name == "anon_1" and index % 2 == 1:
            return completed({**FULL, "Adds": (0.0, 2.0)})
        return completed(FULL)

    view.set_report(_report(tmp_path, script, runs=20))

    adds = view.tree.topLevelItem(0).child(0)
    [anon_1] = _children(adds)
    usual, differing, _all_runs, _folder = _children(anon_1)
    rows = _children(differing)
    assert len(rows) == 11
    assert rows[-1].text(0) == "Show 6 more runs"
    assert [r.isHidden() for r in rows[:RUNS_SHOWN_AT_FIRST]] == [False] * RUNS_SHOWN_AT_FIRST
    assert all(r.isHidden() for r in rows[RUNS_SHOWN_AT_FIRST:-1])

    view.tree.itemClicked.emit(rows[-1], 0)

    rows = _children(differing)
    assert len(rows) == 10
    assert not any(r.isHidden() for r in rows)


def test_a_run_row_opens_everything_the_autograder_printed(view, tmp_path):
    def script(name, index):
        if name == "anon_3" and index == 1:
            return AutograderRunOutcome(
                status=AutograderRunStatus.CRASHED,
                duration_seconds=0.4,
                error="Exited with status 1: ZeroDivisionError: division by zero",
                output_tail=TRACEBACK,
            )
        return completed(FULL)

    view.set_report(_report(tmp_path, script))
    dialogs = []
    view.dialog_launcher = dialogs.append
    [anon_3] = _children(view.tree.topLevelItem(0))
    run = _children(anon_3)[0]
    assert run.text(2) == "crashed · Exited with status 1: ZeroDivisionError: division by zero"
    assert run.toolTip(0) == "Double-click or right-click for the full output"

    menu = view.run_menu(run)
    assert [a.text() for a in menu.actions()] == ["View full output…", "Copy output"]
    menu.actions()[0].trigger()

    [dialog] = dialogs
    assert dialog.title_label.text() == "anon_3 · run 2"
    assert dialog.summary_label.text() == (
        "Crashed after 0.4 s · ser334_m9_grader\n"
        "Exited with status 1: ZeroDivisionError: division by zero"
    )
    assert dialog.output.toPlainText() == TRACEBACK
    assert run_output_text(dialog._execution, "ser334_m9_grader").endswith(TRACEBACK)

    view.tree.itemDoubleClicked.emit(run, 0)

    assert len(dialogs) == 2
    assert view.run_menu(anon_3) is None, "only run rows have the menu"


def test_columns_can_be_dragged(view, tmp_path):
    view.set_report(_report(tmp_path, _mixed))

    header = view.tree.header()
    assert header.sectionResizeMode(0) is QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(1) is QHeaderView.ResizeMode.Interactive
    assert header.sectionResizeMode(2) is QHeaderView.ResizeMode.Interactive
    assert not header.stretchLastSection()


def test_a_cancelled_report_shows_the_banner(view, tmp_path):
    report = _report(tmp_path, lambda n, i: completed(FULL), runs=5, cancelled_at=6)

    view.set_report(report)

    assert report.cancelled
    assert view.banner_label.isVisibleTo(view)
    assert view.banner_label.text().startswith("Cancelled after run 2 of 5")
    assert "3 submissions × 2 runs" in view.meta_label.text()


def test_clear_empties_the_view(view, tmp_path):
    view.set_report(_report(tmp_path, _mixed), tmp_path / "x.json")

    view.clear()

    assert view.report is None
    assert view.tree.topLevelItemCount() == 0
    assert view.saved_label.text() == ""


def test_the_report_verdict_is_what_the_band_shows(tmp_path):
    report = _report(tmp_path, _mixed)

    assert report.verdict is StabilityState.BROKE
    assert [t.state for t in report.tests] == [
        StabilityState.CHANGED,
        StabilityState.PASS,
        StabilityState.CHANGED,
    ]
