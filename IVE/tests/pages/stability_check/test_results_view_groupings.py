from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QHeaderView

from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier
from GAVEL.app.usecases.check_stability import (
    CheckStabilityRequest,
    CheckStabilityUseCase,
    mapping_points_possible,
    proxy_totals,
)
from GAVEL.pages.stability_check.results_view import Grouping, ResultsView, SortOrder
from GAVEL.pages.stability_check.submission_detail_dialog import SubmissionDetailDialog
from tests.fakes.autograder_runner import FakeAutograderRunner, completed, timed_out

FULL = {"Adds": (2.0, 2.0), "Prints": (1.0, 1.0), "Sorts": (3.0, 3.0)}
MAPPING = ProxyGradeMapping(
    name="test_m9",
    criteria=(
        Criterion("arithmetic", (Tier(2.0, all_of=("Adds",)),)),
        Criterion(
            "output",
            (Tier(4.0, all_of=("Prints", "Sorts")), Tier(2.0, any_of=("Prints", "Sorts"))),
        ),
    ),
)


def _mixed(name, index):
    """anon_2 flips Adds on odd runs; anon_3 times out on run 2; anon_1 drops Sorts once."""
    if name == "anon_3" and index == 1:
        return timed_out(300.0)
    if name == "anon_2" and index % 2 == 1:
        return completed({**FULL, "Adds": (0.0, 2.0)})
    if name == "anon_1" and index == 4:
        return completed({**FULL, "Sorts": (1.0, 3.0)})
    return completed(FULL)


def _report(tmp_path: Path, script=_mixed, runs=6, mapping=MAPPING):
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
        mapping=mapping,
    )
    return CheckStabilityUseCase(FakeAutograderRunner(script), lambda: next(times)).execute(request)


@pytest.fixture
def view(qapp, theme) -> ResultsView:
    return ResultsView(theme)


def _top(view: ResultsView) -> list:
    return [view.tree.topLevelItem(i) for i in range(view.tree.topLevelItemCount())]


def _children(item) -> list:
    return [item.child(i) for i in range(item.childCount())]


def _find(items, text: str):
    [item] = [i for i in items if i.text(0) == text]
    return item


# ----- the toggle ------------------------------------------------------------------------------


def test_the_criterion_view_needs_a_mapping(view, tmp_path):
    view.set_report(_report(tmp_path, mapping=None))

    button = view.grouping_buttons[Grouping.CRITERION]
    assert not button.isEnabled()
    assert button.toolTip().startswith("No proxy mapping")
    view.set_grouping(Grouping.CRITERION)
    assert view.grouping is Grouping.TEST

    view.set_report(_report(tmp_path), mapping=MAPPING)

    assert button.isEnabled()


def test_switching_grouping_relabels_the_controls_and_columns(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)

    view.set_grouping(Grouping.SUBMISSION)

    assert view.grouping is Grouping.SUBMISSION
    assert view.show_stable_check.text() == "Show stable submissions"
    assert [view.sort_combo.itemText(i) for i in range(3)] == [
        "Most unstable first",
        "Most tests affected",
        "Anonymous id",
    ]
    assert view.tree.headerItem().text(0) == "Submission"
    assert view.tree.headerItem().text(3) == "Proxy total seen"

    view.set_grouping(Grouping.CRITERION)

    assert view.tree.headerItem().text(2) == "Points seen"
    assert view.sort_combo.itemText(2) == "Criterion name"


def test_columns_can_be_dragged_in_every_grouping(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)
    view.set_grouping(Grouping.SUBMISSION)

    header = view.tree.header()
    assert header.sectionResizeMode(0) is QHeaderView.ResizeMode.Stretch
    assert all(
        header.sectionResizeMode(column) is QHeaderView.ResizeMode.Interactive
        for column in range(1, 4)
    )
    assert not header.stretchLastSection()


# ----- by rubric criterion -------------------------------------------------------------------


def test_criteria_are_grouped_with_points_seen_and_built_from(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)
    view.set_grouping(Grouping.CRITERION)

    tops = _top(view)
    assert tops[0].text(0).startswith("Changed · 2 criteria")
    assert len(tops) == 1  # no stable criteria to hide, no broke group without all-broke criteria

    arithmetic = _find(_children(tops[0]), "arithmetic")
    assert arithmetic.text(2) == "2 or 0"
    assert arithmetic.text(3) == "1 of 3"
    assert view.tree.itemWidget(arithmetic, 1).text == "78% · 14/18"

    built_from, anon_2 = _children(arithmetic)
    assert built_from.text(0) == "Built from"
    [adds] = _children(built_from)
    assert adds.text(0) == "Adds"
    assert adds.text(2) == "needed for 2"
    assert adds.text(3) == "In test view"
    assert anon_2.text(0) == "anon_2"
    assert anon_2.text(2) == "2/2 pts ×3 · 0/2 pts ×3"

    output = _find(_children(tops[0]), "output")
    [prints, sorts] = _children(_children(output)[0])
    assert prints.text(2) == "needed for 4, one of 2 for 2"
    assert sorts.text(2) == "needed for 4, one of 2 for 2"


def test_in_test_view_jumps_to_that_test(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)
    view.set_grouping(Grouping.CRITERION)
    output = _find(_children(_top(view)[0]), "output")
    [_, sorts] = _children(_children(output)[0])

    view.tree.itemClicked.emit(sorts, 3)

    assert view.grouping is Grouping.TEST
    current = view.tree.currentItem()
    assert current is not None
    assert current.text(0) == "Sorts"
    assert current.isExpanded()


def test_jumping_to_a_stable_test_reveals_the_stable_group(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)
    assert not view.show_stable_check.isChecked()

    view.show_test("Prints")

    assert view.show_stable_check.isChecked()
    assert view.tree.currentItem().text(0) == "Prints"


# ----- by submission -------------------------------------------------------------------------


def test_submissions_are_grouped_with_their_unstable_tests(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)
    view.set_grouping(Grouping.SUBMISSION)

    tops = _top(view)
    assert [t.text(0) for t in tops] == ["Broke · 1 submission", "Changed · 2 submissions"]
    assert tops[1].toolTip(0) == (
        "Changed: scored differently on different runs of at least one test."
    )

    [anon_3] = _children(tops[0])
    assert anon_3.text(1) == "0 of 3"
    assert view.tree.itemWidget(anon_3, 2).text == "83% · 15/18"
    assert anon_3.text(3) == "6 of 6"
    note, folder, inspect = _children(anon_3)
    assert note.text(0) == "Runs with no result · timed out ×1"
    assert [r.text(0) for r in _children(note)] == ["Run 2"]
    assert folder.text(0) == "Open submission folder"
    assert inspect.text(0) == "View in Inspect Grades"

    anon_2 = _find(_children(tops[1]), "anon_2")
    assert anon_2.text(1) == "1 of 3"
    assert anon_2.text(3) == "4 to 6 of 6"
    assert view.tree.itemWidget(anon_2, 2).text == "83% · 15/18"
    adds, folder, inspect = _children(anon_2)
    assert adds.text(0) == "Adds"
    assert inspect.text(0) == "View in Inspect Grades"
    assert adds.text(3) == "2/2 pts ×3 · 0/2 pts ×3"
    assert [a.text(0) for a in _children(adds)] == ["All runs", "In test view"]

    anon_1 = _find(_children(tops[1]), "anon_1")
    assert anon_1.text(1) == "1 of 3"
    assert anon_1.text(3) == "4 to 6 of 6"


def test_stable_submissions_hide_until_asked(view, tmp_path):
    view.set_report(_report(tmp_path, script=lambda n, i: completed(FULL), runs=3), mapping=MAPPING)
    view.set_grouping(Grouping.SUBMISSION)

    [stable] = _top(view)
    assert stable.text(0).startswith("Stable · 3 submissions")
    assert stable.childCount() == 0

    view.show_stable_check.setChecked(True)

    rows = _children(_top(view)[0])
    assert [r.text(0) for r in rows] == ["anon_1", "anon_2", "anon_3"]
    assert rows[0].text(3) == "6 of 6"


def test_submission_sorting(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)
    view.set_grouping(Grouping.SUBMISSION)

    changed = _top(view)[1]
    assert [r.text(0) for r in _children(changed)] == ["anon_2", "anon_1"]  # worst first

    view.sort_combo.setCurrentIndex(list(SortOrder).index(SortOrder.NAME))
    assert [r.text(0) for r in _children(_top(view)[1])] == ["anon_1", "anon_2"]

    view.sort_combo.setCurrentIndex(list(SortOrder).index(SortOrder.MOST_AFFECTED))
    assert [r.text(0) for r in _children(_top(view)[1])] == ["anon_2", "anon_1"]
    assert _top(view)[0].text(0).startswith("Broke")


# ----- actions -------------------------------------------------------------------------------


def test_open_folder_rows_emit_the_submission_name(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)
    asked = []
    view.open_folder_requested.connect(asked.append)
    adds = _find(_children(_top(view)[1]), "Adds")
    [anon_2] = _children(adds)
    folder_row = _children(anon_2)[-2]
    assert folder_row.text(0) == "Open submission folder"

    view.tree.itemClicked.emit(folder_row, 0)

    assert asked == ["anon_2"]


def test_all_runs_opens_the_detail_dialog(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)
    opened = []
    view.dialog_launcher = opened.append
    adds = _find(_children(_top(view)[1]), "Adds")
    [anon_2] = _children(adds)
    all_runs = _children(anon_2)[-3]
    assert all_runs.text(0) == "All runs"

    view.tree.itemClicked.emit(all_runs, 0)

    [dialog] = opened
    assert isinstance(dialog, SubmissionDetailDialog)
    assert dialog.title_label.text() == "anon_2 · Adds"
    assert dialog.summary_label.text().startswith("3 of 6 runs agreed · usual result 2/2 pts")
    groups = [dialog.tree.topLevelItem(i) for i in range(dialog.tree.topLevelItemCount())]
    assert [g.text(0) for g in groups] == [
        "2/2 pts · usual result",
        "0/2 pts · differs from the usual result",
    ]
    assert [g.text(1) for g in groups] == ["3 runs", "3 runs"]
    assert [r.text(0) for r in _children(groups[1])] == ["Run 2", "Run 4", "Run 6"]
    assert _children(groups[1])[0].text(1) == "1.0 s"
    assert dialog.open_folder_button.isVisibleTo(dialog)

    # A run row in the dialog opens its full output the same way as in the tree.
    run_dialogs = []
    dialog.dialog_launcher = run_dialogs.append
    run_row = _children(groups[1])[0]
    assert dialog.run_menu(groups[1]) is None
    dialog.run_menu(run_row).actions()[0].trigger()
    dialog.tree.itemDoubleClicked.emit(run_row, 0)
    assert [d.title_label.text() for d in run_dialogs] == ["anon_2 · run 2", "anon_2 · run 2"]
    assert run_dialogs[0].summary_label.text() == "Completed after 1.0 s · ser334_m9_grader"

    asked = []
    view.open_folder_requested.connect(asked.append)
    dialog.open_folder_button.click()
    assert asked == ["anon_2"]
    dialog.close_button.click()
    assert dialog.result() == dialog.DialogCode.Accepted


# ----- helpers in the use case ---------------------------------------------------------------


def test_proxy_totals_give_each_submissions_range(tmp_path):
    report = _report(tmp_path)

    totals = proxy_totals(report, MAPPING)

    assert totals == {"anon_1": (4.0, 6.0), "anon_2": (4.0, 6.0), "anon_3": (6.0, 6.0)}
    assert mapping_points_possible(MAPPING) == 6.0


def test_view_in_inspect_grades_hands_off_the_submission(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)
    asked = []
    view.inspect_requested.connect(asked.append)
    adds = _find(_children(_top(view)[1]), "Adds")
    [anon_2] = _children(adds)
    inspect_row = _children(anon_2)[-1]
    assert inspect_row.text(0) == "View in Inspect Grades"

    view.tree.itemClicked.emit(inspect_row, 0)

    assert asked == ["anon_2"]

    # The By submission view and the broken group offer it too.
    view.set_grouping(Grouping.SUBMISSION)
    [anon_3] = _children(_top(view)[0])
    view.tree.itemClicked.emit(_children(anon_3)[-1], 0)

    assert asked == ["anon_2", "anon_3"]


def test_the_dialog_hands_off_and_closes(view, tmp_path):
    view.set_report(_report(tmp_path), mapping=MAPPING)
    opened = []
    view.dialog_launcher = opened.append
    asked = []
    view.inspect_requested.connect(asked.append)
    adds = _find(_children(_top(view)[1]), "Adds")
    [anon_2] = _children(adds)
    view.tree.itemClicked.emit(_children(anon_2)[-3], 0)
    [dialog] = opened
    assert dialog.inspect_button.isVisibleTo(dialog)

    dialog.inspect_button.click()

    assert asked == ["anon_2"]
    assert dialog.result() == dialog.DialogCode.Accepted
