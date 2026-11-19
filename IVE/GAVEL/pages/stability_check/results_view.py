"""The results of a stability check: a verdict band and a tree, grouped three ways.

By test is the main view: test, then the submissions that disagreed, then one
row per distinct result, then the runs that gave it. By rubric criterion is the
same tree over the proxy mapping's criteria, with the tests each criterion is
built from. By submission puts the student first, with the tests that varied
for them and the runs that broke.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.dtos.proxy_grade_mapping import ProxyGradeMapping
from GAVEL.app.dtos.stability import (
    ExecutionRecord,
    ItemStability,
    ResultSeen,
    StabilityReport,
    StabilityState,
    SubmissionItemStability,
    SubmissionStability,
)
from GAVEL.app.usecases.check_stability import mapping_points_possible, proxy_totals
from GAVEL.app.usecases.proxy_grade.mappings.registry import MAPPINGS
from GAVEL.pages.stability_check.agreement_bar import AgreementCell
from GAVEL.pages.stability_check.run_output_dialog import RunOutputDialog, run_output_text
from GAVEL.pages.stability_check.submission_detail_dialog import SubmissionDetailDialog
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing

RUNS_SHOWN_AT_FIRST = 4
_KIND = Qt.ItemDataRole.UserRole
_PAYLOAD = Qt.ItemDataRole.UserRole + 1
_RUN_TOOLTIP = "Double-click or right-click for the full output"


class Grouping(Enum):
    TEST = "By test"
    CRITERION = "By rubric criterion"
    SUBMISSION = "By submission"


class SortOrder(Enum):
    WORST_FIRST = "worst_first"
    MOST_AFFECTED = "most_affected"
    NAME = "name"


_SORT_LABELS = {
    Grouping.TEST: {
        SortOrder.WORST_FIRST: "Worst first",
        SortOrder.MOST_AFFECTED: "Most submissions affected",
        SortOrder.NAME: "Test name",
    },
    Grouping.CRITERION: {
        SortOrder.WORST_FIRST: "Worst first",
        SortOrder.MOST_AFFECTED: "Most submissions affected",
        SortOrder.NAME: "Criterion name",
    },
    Grouping.SUBMISSION: {
        SortOrder.WORST_FIRST: "Most unstable first",
        SortOrder.MOST_AFFECTED: "Most tests affected",
        SortOrder.NAME: "Anonymous id",
    },
}
_HEADERS = {
    Grouping.TEST: ["Test", "Runs agreed", "Submissions"],
    Grouping.CRITERION: ["Criterion", "Runs agreed", "Points seen", "Submissions"],
    Grouping.SUBMISSION: [
        "Submission",
        "Tests affected",
        "Runs agreed · all tests",
        "Proxy total seen",
    ],
}
_BAR_COLUMN = {Grouping.TEST: 1, Grouping.CRITERION: 1, Grouping.SUBMISSION: 2}
_NOUN = {Grouping.TEST: "tests", Grouping.CRITERION: "criteria", Grouping.SUBMISSION: "submissions"}
_BADGE = {
    StabilityState.PASS: ("STABLE", "status_nominal"),
    StabilityState.CHANGED: ("UNSTABLE", "status_caution"),
    StabilityState.BROKE: ("BROKEN", "status_critical"),
}
_DOT = {
    StabilityState.PASS: "status_nominal",
    StabilityState.CHANGED: "status_caution",
    StabilityState.BROKE: "status_critical",
}
_GROUP_LABEL = {
    StabilityState.BROKE: "Broke",
    StabilityState.CHANGED: "Changed",
    StabilityState.PASS: "Stable",
}
_GROUP_NOTE = {
    (
        Grouping.TEST,
        StabilityState.BROKE,
    ): "the autograder timed out or crashed on at least one run",
    (
        Grouping.TEST,
        StabilityState.CHANGED,
    ): "the same submission scored differently on different runs",
    (
        Grouping.TEST,
        StabilityState.PASS,
    ): "the same result on every completed run for every submission",
    (Grouping.CRITERION, StabilityState.BROKE): "no completed run gave these criteria any points",
    (
        Grouping.CRITERION,
        StabilityState.CHANGED,
    ): "the same submission earned different points on different runs",
    (
        Grouping.CRITERION,
        StabilityState.PASS,
    ): "the same points on every completed run for every submission",
    (
        Grouping.SUBMISSION,
        StabilityState.BROKE,
    ): "the autograder timed out or crashed on at least one of their runs",
    (
        Grouping.SUBMISSION,
        StabilityState.CHANGED,
    ): "scored differently on different runs of at least one test",
    (
        Grouping.SUBMISSION,
        StabilityState.PASS,
    ): "every test gave the same result on all of their runs",
}

FOOTNOTE = (
    "Broke: the autograder timed out or crashed on at least one run. Changed: the same "
    "submission scored differently on different runs. Stable: the same result on every "
    "completed run for every submission. Runs agreed counts every execution that matched the "
    "submission's usual result for that item; a run with no result counts against it. Points "
    "come from the assignment's proxy mapping. Double-click or right-click a run for everything "
    "the autograder printed."
)


class ResultsView(QWidget):
    open_folder_requested = pyqtSignal(str)  # a submission's folder name

    def __init__(self, theme: ThemeContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._report: StabilityReport | None = None
        self._mapping: ProxyGradeMapping | None = None
        self._executions: dict[tuple[str, int], ExecutionRecord] = {}
        self._rendering = False
        # Swapped out in tests so no modal dialog blocks.
        self.dialog_launcher: Callable[[QDialog], None] = lambda dialog: dialog.exec()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        set_spacing(root, theme, 12)
        root.addWidget(self._build_band())
        root.addWidget(self._build_controls())
        self.tree = QTreeWidget()
        self.tree.setMinimumHeight(320)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        root.addWidget(self.tree)
        self.footnote = QLabel(FOOTNOTE)
        self.footnote.setProperty("role", "text_muted")
        self.footnote.setWordWrap(True)
        root.addWidget(self.footnote)
        self.saved_label = QLabel()
        self.saved_label.setProperty("role", "text_muted")
        self.saved_label.setWordWrap(True)
        root.addWidget(self.saved_label)
        self._apply_grouping_to_controls()

    # ----- building ----------------------------------------------------------------------------

    def _build_band(self) -> QWidget:
        band = QFrame()
        band.setProperty("role", "surface")
        layout = QVBoxLayout(band)
        set_spacing(layout, self._theme, 8)

        top = QHBoxLayout()
        set_spacing(top, self._theme, 12)
        self.verdict_badge = QLabel()
        self.verdict_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.verdict_badge.setMinimumWidth(96)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.headline_label = QLabel()
        self.headline_label.setProperty("role", "h2")
        self.headline_label.setWordWrap(True)
        self.meta_label = QLabel()
        self.meta_label.setProperty("role", "text_muted")
        self.meta_label.setWordWrap(True)
        text.addWidget(self.headline_label)
        text.addWidget(self.meta_label)
        top.addWidget(self.verdict_badge, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(text, 1)
        layout.addLayout(top)

        # One wrapping label rather than four rigid ones, so the tiles flow onto a
        # second line in a narrow window instead of forcing the page wider.
        self.tiles_label = QLabel()
        self.tiles_label.setProperty("role", "readout_value")
        self.tiles_label.setTextFormat(Qt.TextFormat.RichText)
        self.tiles_label.setWordWrap(True)
        self.tile_texts: dict[str, str] = {}
        layout.addWidget(self.tiles_label)

        self.banner_label = QLabel()
        self.banner_label.setProperty("role", "text_muted")
        self.banner_label.setWordWrap(True)
        self.banner_label.hide()
        layout.addWidget(self.banner_label)
        return band

    def _build_controls(self) -> QWidget:
        # Two rows, grouping and then sort, so the controls fit a narrow window.
        controls = QWidget()
        layout = QVBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(layout, self._theme, 8)
        grouping_row = QHBoxLayout()
        set_spacing(grouping_row, self._theme, 12)
        sort_row = QHBoxLayout()
        set_spacing(sort_row, self._theme, 12)
        layout.addLayout(grouping_row)
        layout.addLayout(sort_row)

        self.grouping_group = QButtonGroup(self)
        self.grouping_group.setExclusive(True)
        self.grouping_buttons: dict[Grouping, QPushButton] = {}
        for index, grouping in enumerate(Grouping):
            button = QPushButton(grouping.value)
            button.setCheckable(True)
            button.setProperty("role", "secondary")
            self.grouping_group.addButton(button, index)
            self.grouping_buttons[grouping] = button
            grouping_row.addWidget(button)
        grouping_row.addStretch(1)
        self.grouping_buttons[Grouping.TEST].setChecked(True)
        self.grouping_group.idClicked.connect(lambda _: self._on_controls_changed())

        sort_label = QLabel("Sort")
        sort_label.setProperty("role", "text_muted")
        self.sort_combo = QComboBox()
        for order in SortOrder:
            self.sort_combo.addItem(order.value, order)
        # Shows the whole order name when open; closed, it may be narrower than that.
        self.sort_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.sort_combo.setMinimumContentsLength(14)
        self.sort_combo.currentIndexChanged.connect(lambda _: self._on_controls_changed())
        self.show_stable_check = QCheckBox()
        self.show_stable_check.toggled.connect(lambda _: self._on_controls_changed())
        sort_row.addWidget(sort_label)
        sort_row.addWidget(self.sort_combo)
        sort_row.addWidget(self.show_stable_check)
        sort_row.addStretch(1)
        return controls

    # ----- controls ------------------------------------------------------------------------------

    @property
    def grouping(self) -> Grouping:
        for grouping, button in self.grouping_buttons.items():
            if button.isChecked():
                return grouping
        return Grouping.TEST

    def set_grouping(self, grouping: Grouping) -> None:
        button = self.grouping_buttons[grouping]
        if not button.isEnabled():
            return
        button.setChecked(True)
        self._on_controls_changed()

    @property
    def sort_order(self) -> SortOrder:
        return self.sort_combo.currentData()

    def _on_controls_changed(self) -> None:
        if self._rendering:
            return
        self._apply_grouping_to_controls()
        self._rebuild()

    def _apply_grouping_to_controls(self) -> None:
        grouping = self.grouping
        self._rendering = True
        try:
            for index in range(self.sort_combo.count()):
                order = self.sort_combo.itemData(index)
                self.sort_combo.setItemText(index, _SORT_LABELS[grouping][order])
            self.show_stable_check.setText(f"Show stable {_NOUN[grouping]}")
            self.tree.setColumnCount(len(_HEADERS[grouping]))
            self.tree.setHeaderLabels(_HEADERS[grouping])
            # The first column takes what the others leave; the others can be dragged.
            header = self.tree.header()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for column in range(1, len(_HEADERS[grouping])):
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(_BAR_COLUMN[grouping], 220)
        finally:
            self._rendering = False

    def _size_columns_to_contents(self) -> None:
        """Start the text columns at their content width; the user drags them from there."""
        grouping = self.grouping
        for column in range(1, len(_HEADERS[grouping])):
            if column != _BAR_COLUMN[grouping]:
                self.tree.resizeColumnToContents(column)

    # ----- showing a report --------------------------------------------------------------------

    @property
    def report(self) -> StabilityReport | None:
        return self._report

    def set_report(
        self,
        report: StabilityReport,
        saved_to: Path | None = None,
        mapping: ProxyGradeMapping | None = None,
    ) -> None:
        self._report = report
        self._mapping = mapping or (
            MAPPINGS.get(report.mapping_name) if report.mapping_name else None
        )
        self._executions = {(e.submission, e.run): e for e in report.executions}
        self._render_band(report)
        self.saved_label.setText(f"Saved to {saved_to}" if saved_to else "")
        criterion_button = self.grouping_buttons[Grouping.CRITERION]
        if report.criteria:
            criterion_button.setEnabled(True)
            criterion_button.setToolTip("")
        else:
            criterion_button.setEnabled(False)
            criterion_button.setToolTip(
                "No proxy mapping for this assignment, so there are no criteria."
            )
            if self.grouping is Grouping.CRITERION:
                self.grouping_buttons[Grouping.TEST].setChecked(True)
        self._apply_grouping_to_controls()
        self._rebuild()

    def clear(self) -> None:
        self._report = None
        self._mapping = None
        self._executions = {}
        self.tree.clear()
        self.saved_label.clear()

    def show_test(self, name: str) -> None:
        """Switch to the test view with that test expanded and in view."""
        if self._report is None:
            return
        if any(t.name == name and t.state is StabilityState.PASS for t in self._report.tests):
            self.show_stable_check.setChecked(True)
        self.set_grouping(Grouping.TEST)
        for group in self._top_items():
            for index in range(group.childCount()):
                item = group.child(index)
                if item.data(0, _KIND) == "test" and item.text(0) == name:
                    item.setExpanded(True)
                    self.tree.setCurrentItem(item)
                    self.tree.scrollToItem(item)
                    return

    def _render_band(self, report: StabilityReport) -> None:
        colors = self._theme.tokens.color
        text, token = _BADGE[report.verdict]
        self.verdict_badge.setText(text)
        self.verdict_badge.setStyleSheet(
            f"background: {colors[token]}; color: {colors['input_bg']}; "
            "font-weight: 700; padding: 6px 12px; border-radius: 2px;"
        )
        self.headline_label.setText(_headline(report))
        self.meta_label.setText(_meta(report))
        counts = {
            "stable": (len(report.tests_in(StabilityState.PASS)), "tests", "status_nominal"),
            "changed": (len(report.tests_in(StabilityState.CHANGED)), "tests", "status_caution"),
            "broke": (len(report.broken_submissions), "submissions", "status_critical"),
        }
        tiles = []
        for key, (count, noun, token) in counts.items():
            self.tile_texts[key] = f"{key.capitalize()} {count} {noun}"
            tiles.append(
                f'<span style="color:{colors[token]}">●</span>&nbsp;{key.capitalize()}&nbsp;'
                f"<b>{count}</b>&nbsp;{noun}"
            )
        affected, total = report.submissions_affected, len(report.submissions)
        self.tile_texts["affected"] = f"Affected {affected} of {total} submissions"
        tiles.append(f"Affected&nbsp;<b>{affected}</b>&nbsp;of&nbsp;{total}&nbsp;submissions")
        # Plain spaces between tiles are where a line may break; none within a tile.
        self.tiles_label.setText(" &nbsp;&nbsp; ".join(tiles))
        if report.cancelled:
            self.banner_label.setText(
                f"Cancelled after run {report.runs_completed} of {report.runs_requested}; "
                "agreement counts finished runs only."
            )
            self.banner_label.show()
        else:
            self.banner_label.hide()

    # ----- the tree ---------------------------------------------------------------------------

    def _top_items(self) -> list[QTreeWidgetItem]:
        return [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]

    def _rebuild(self) -> None:
        self.tree.clear()
        if self._report is None:
            return
        grouping = self.grouping
        if grouping is Grouping.TEST:
            self._build_by_item(self._report.tests, grouping)
        elif grouping is Grouping.CRITERION:
            self._build_by_item(self._report.criteria, grouping)
        else:
            self._build_by_submission()
        self._size_columns_to_contents()

    def _build_by_item(self, items: tuple[ItemStability, ...], grouping: Grouping) -> None:
        report = self._report
        assert report is not None
        if grouping is Grouping.TEST and report.broken_submissions:
            group = self._group(StabilityState.BROKE, len(report.broken_submissions), grouping)
            for submission in report.broken_submissions:
                self._add_broken_submission(group, submission)
            group.setExpanded(True)
        for state in (StabilityState.BROKE, StabilityState.CHANGED, StabilityState.PASS):
            if grouping is Grouping.TEST and state is StabilityState.BROKE:
                continue
            in_state = tuple(i for i in items if i.state is state)
            if not in_state:
                continue
            show = state is not StabilityState.PASS or self.show_stable_check.isChecked()
            group = self._group(state, len(in_state), grouping, listed=show)
            if not show:
                continue
            for item in self._sorted(in_state):
                self._add_item(group, item, grouping)
            group.setExpanded(True)

    def _group(
        self, state: StabilityState, count: int, grouping: Grouping, listed: bool = True
    ) -> QTreeWidgetItem:
        noun = (
            "submissions"
            if state is StabilityState.BROKE and grouping is Grouping.TEST
            else _NOUN[grouping]
        )
        if count == 1:
            noun = {"tests": "test", "criteria": "criterion", "submissions": "submission"}[noun]
        text = f"{_GROUP_LABEL[state]} · {count} {noun}"
        if not listed:
            text += f" · tick Show stable {_NOUN[grouping]} to list them"
        item = QTreeWidgetItem([text])
        # The definition lives in the tooltip and the footnote, so the row stays short.
        item.setToolTip(0, f"{_GROUP_LABEL[state]}: {_GROUP_NOTE[(grouping, state)]}.")
        item.setFirstColumnSpanned(True)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = QFont()
        font.setBold(True)
        item.setFont(0, font)
        item.setForeground(0, self._brush(_DOT[state]))
        item.setData(0, _KIND, "group")
        self.tree.addTopLevelItem(item)
        return item

    def _sorted(self, items: tuple[ItemStability, ...]) -> list[ItemStability]:
        order = self.sort_order
        if order is SortOrder.NAME:
            return sorted(items, key=lambda t: t.name.lower())
        if order is SortOrder.MOST_AFFECTED:
            return sorted(items, key=lambda t: (-t.submissions_affected, t.agreement, t.name))
        return sorted(items, key=lambda t: (t.agreement, -t.runs_broke, t.name))

    def _add_item(self, group: QTreeWidgetItem, item: ItemStability, grouping: Grouping) -> None:
        affected = f"{item.submissions_affected} of {item.submissions_total}"
        if grouping is Grouping.CRITERION:
            texts = [item.name, "", _points_seen(item), affected]
        else:
            texts = [item.name, "", affected]
        row = QTreeWidgetItem(texts)
        row.setData(0, _KIND, "test" if grouping is Grouping.TEST else "criterion")
        row.setForeground(0, self._brush(_DOT[item.state]))
        group.addChild(row)
        self.tree.setItemWidget(
            row,
            1,
            AgreementCell(
                self._theme,
                item.runs_agreed,
                item.runs_changed,
                item.runs_broke,
                f"{round(item.agreement * 100)}% · {item.runs_agreed}/{item.runs_total}",
            ),
        )
        if grouping is Grouping.CRITERION:
            self._add_built_from(row, item)
        for entry in item.affected:
            self._add_submission(row, entry, item.name, grouping)

    def _add_built_from(self, parent: QTreeWidgetItem, criterion: ItemStability) -> None:
        report = self._report
        assert report is not None
        header = QTreeWidgetItem(["Built from"])
        header.setFirstColumnSpanned(True)
        header.setFlags(Qt.ItemFlag.ItemIsEnabled)
        header.setForeground(0, self._brush("text_secondary"))
        header.setData(0, _KIND, "note")
        parent.addChild(header)
        for prefix in criterion.built_from:
            tests = [t for t in report.tests if t.name.startswith(prefix)] or None
            note = _tier_note(self._mapping, criterion.name, prefix)
            if tests is None:
                row = QTreeWidgetItem([prefix, "", note, "not in this autograder's results"])
                row.setData(0, _KIND, "note")
                header.addChild(row)
                continue
            for test in tests:
                row = QTreeWidgetItem([test.name, "", note, "In test view"])
                row.setData(0, _KIND, "in-test-view")
                row.setData(0, _PAYLOAD, test.name)
                row.setForeground(0, self._brush(_DOT[test.state]))
                row.setForeground(3, self._brush("text_link"))
                header.addChild(row)
                self.tree.setItemWidget(
                    row,
                    1,
                    AgreementCell(
                        self._theme,
                        test.runs_agreed,
                        test.runs_changed,
                        test.runs_broke,
                        f"{round(test.agreement * 100)}% · {test.runs_agreed}/{test.runs_total}",
                    ),
                )
        header.setExpanded(True)

    def _add_submission(
        self,
        parent: QTreeWidgetItem,
        entry: SubmissionItemStability,
        item_name: str,
        grouping: Grouping,
    ) -> None:
        texts = [entry.submission, "", _results_seen(entry)]
        if grouping is Grouping.CRITERION:
            texts = [entry.submission, "", _results_seen(entry), ""]
        row = QTreeWidgetItem(texts)
        row.setData(0, _KIND, "submission")
        parent.addChild(row)
        self.tree.setItemWidget(row, 1, self._cell_for(entry))
        for index, result in enumerate(entry.results):
            self._add_result(row, result, entry.submission, item_name, usual=index == 0)
        self._add_action(row, "All runs", "all-runs", (item_name, entry))
        self._add_action(row, "Open submission folder", "open-folder", entry.submission)

    def _cell_for(self, entry: SubmissionItemStability) -> AgreementCell:
        return AgreementCell(
            self._theme,
            entry.runs_agreed,
            entry.runs_total - entry.runs_agreed - entry.runs_broke,
            entry.runs_broke,
            f"{entry.runs_agreed}/{entry.runs_total}",
        )

    def _add_result(
        self,
        parent: QTreeWidgetItem,
        result: ResultSeen,
        submission: str,
        item_name: str,
        usual: bool,
    ) -> None:
        if result.score is None:
            note = "no result: timed out or crashed"
        elif usual:
            note = "usual result"
        else:
            note = "differs from the usual result"
        if result.output:
            note = f"{note} · output: {result.output}"
        row = QTreeWidgetItem([f"{_points(result)} · {note}", "", f"{len(result.runs)} runs"])
        row.setData(0, _KIND, "result")
        parent.addChild(row)
        self._add_runs(
            row, submission, result.runs, lambda run: self._run_text(submission, run, item_name)
        )

    def _add_broken_submission(
        self, group: QTreeWidgetItem, submission: SubmissionStability
    ) -> None:
        parts = []
        if submission.runs_timed_out:
            parts.append(f"timed out ×{submission.runs_timed_out}")
        if submission.runs_crashed:
            parts.append(f"crashed ×{submission.runs_crashed}")
        row = QTreeWidgetItem([submission.name, "", " · ".join(parts)])
        row.setData(0, _KIND, "submission")
        group.addChild(row)
        self.tree.setItemWidget(
            row,
            1,
            AgreementCell(
                self._theme,
                submission.runs_completed,
                0,
                submission.runs_broke,
                f"{submission.runs_completed}/{submission.runs_total}",
            ),
        )
        self._add_broken_runs(row, submission.name)
        self._add_action(row, "Open submission folder", "open-folder", submission.name)

    def _add_broken_runs(self, parent: QTreeWidgetItem, submission: str) -> None:
        runs = tuple(
            e.run
            for e in sorted(self._executions.values(), key=lambda e: e.run)
            if e.submission == submission and not e.completed
        )
        self._add_runs(parent, submission, runs, lambda run: self._run_text(submission, run, None))

    def _add_runs(
        self, parent: QTreeWidgetItem, submission: str, runs: tuple[int, ...], text_of
    ) -> None:
        for index, run in enumerate(runs):
            row = QTreeWidgetItem([f"Run {run}", "", text_of(run)])
            row.setData(0, _KIND, "run")
            row.setData(0, _PAYLOAD, (submission, run))
            for column in range(self.tree.columnCount()):
                row.setToolTip(column, _RUN_TOOLTIP)
            parent.addChild(row)
            if index >= RUNS_SHOWN_AT_FIRST:
                row.setHidden(True)
        hidden = len(runs) - RUNS_SHOWN_AT_FIRST
        if hidden > 0:
            self._add_action(parent, f"Show {hidden} more runs", "show-more", None)

    def _add_action(self, parent: QTreeWidgetItem, text: str, kind: str, payload) -> None:
        row = QTreeWidgetItem([text])
        row.setFirstColumnSpanned(True)
        row.setData(0, _KIND, kind)
        row.setData(0, _PAYLOAD, payload)
        row.setForeground(0, self._brush("text_link"))
        parent.addChild(row)

    # ----- by submission --------------------------------------------------------------------------

    def _build_by_submission(self) -> None:
        report = self._report
        assert report is not None
        totals = proxy_totals(report, self._mapping) if self._mapping else {}
        possible = mapping_points_possible(self._mapping) if self._mapping else None
        rows = [_SubmissionRow.of(report, s) for s in report.submissions]
        for state in (StabilityState.BROKE, StabilityState.CHANGED, StabilityState.PASS):
            in_state = [r for r in rows if r.state is state]
            if not in_state:
                continue
            show = state is not StabilityState.PASS or self.show_stable_check.isChecked()
            group = self._group(state, len(in_state), Grouping.SUBMISSION, listed=show)
            if not show:
                continue
            for row in self._sorted_submissions(in_state):
                self._add_submission_row(group, row, totals.get(row.name), possible)
            group.setExpanded(True)

    def _sorted_submissions(self, rows: list[_SubmissionRow]) -> list[_SubmissionRow]:
        order = self.sort_order
        if order is SortOrder.NAME:
            return sorted(rows, key=lambda r: r.name.lower())
        if order is SortOrder.MOST_AFFECTED:
            return sorted(rows, key=lambda r: (-len(r.affected), r.agreement, r.name))
        return sorted(rows, key=lambda r: (r.agreement, -r.broke, r.name))

    def _add_submission_row(
        self,
        group: QTreeWidgetItem,
        row: _SubmissionRow,
        total_range: tuple[float, float] | None,
        possible: float | None,
    ) -> None:
        report = self._report
        assert report is not None
        item = QTreeWidgetItem(
            [
                row.name,
                f"{len(row.affected)} of {len(report.tests)}",
                "",
                _total_text(total_range, possible),
            ]
        )
        item.setData(0, _KIND, "submission")
        item.setForeground(0, self._brush(_DOT[row.state]))
        group.addChild(item)
        self.tree.setItemWidget(
            item,
            2,
            AgreementCell(
                self._theme,
                row.agreed,
                row.changed,
                row.broke,
                f"{round(row.agreement * 100)}% · {row.agreed}/{row.total}",
            ),
        )
        for test, entry in row.affected:
            test_row = QTreeWidgetItem([test.name, "", "", _results_seen(entry)])
            test_row.setData(0, _KIND, "in-test-view")
            test_row.setData(0, _PAYLOAD, test.name)
            test_row.setForeground(0, self._brush(_DOT[test.state]))
            item.addChild(test_row)
            self.tree.setItemWidget(test_row, 2, self._cell_for(entry))
            self._add_action(test_row, "All runs", "all-runs", (test.name, entry))
            self._add_action(test_row, "In test view", "in-test-view", test.name)
        if row.broke:
            broke_row = QTreeWidgetItem([f"Runs with no result · {row.broke_text}"])
            broke_row.setFirstColumnSpanned(True)
            broke_row.setData(0, _KIND, "note")
            broke_row.setForeground(0, self._brush("status_critical"))
            item.addChild(broke_row)
            self._add_broken_runs(broke_row, row.name)
        self._add_action(item, "Open submission folder", "open-folder", row.name)

    # ----- clicks -----------------------------------------------------------------------------

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        kind = item.data(0, _KIND)
        payload = item.data(0, _PAYLOAD)
        if kind == "show-more":
            parent = item.parent()
            if parent is not None:
                for index in range(parent.childCount()):
                    parent.child(index).setHidden(False)
                parent.removeChild(item)
        elif kind == "in-test-view":
            self.show_test(payload)
        elif kind == "open-folder":
            self.open_folder_requested.emit(payload)
        elif kind == "all-runs" and self._report is not None:
            item_name, entry = payload
            dialog = SubmissionDetailDialog(
                self,
                self._theme,
                self._report,
                item_name,
                entry,
                open_folder=self.open_folder_requested.emit,
            )
            self.dialog_launcher(dialog)

    # ----- a run's full output ----------------------------------------------------------------

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if item.data(0, _KIND) == "run":
            self.open_run_output(*item.data(0, _PAYLOAD))

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.tree.itemAt(pos)
        menu = self.run_menu(item) if item is not None else None
        if menu is not None:
            menu.exec(self.tree.viewport().mapToGlobal(pos))

    def run_menu(self, item: QTreeWidgetItem) -> QMenu | None:
        """The context menu of a run row: view or copy its output. None for any other row."""
        if item.data(0, _KIND) != "run":
            return None
        submission, run = item.data(0, _PAYLOAD)
        menu = QMenu(self.tree)
        view = menu.addAction("View full output…")
        view.triggered.connect(lambda: self.open_run_output(submission, run))
        copy = menu.addAction("Copy output")
        copy.triggered.connect(lambda: self.copy_run_output(submission, run))
        return menu

    def open_run_output(self, submission: str, run: int) -> None:
        execution = self._executions.get((submission, run))
        if execution is None or self._report is None:
            return
        dialog = RunOutputDialog(self, self._theme, execution, self._report.autograder)
        self.dialog_launcher(dialog)

    def copy_run_output(self, submission: str, run: int) -> None:
        execution = self._executions.get((submission, run))
        if execution is not None and self._report is not None:
            QApplication.clipboard().setText(run_output_text(execution, self._report.autograder))

    def _run_text(self, submission: str, run: int, item_name: str | None) -> str:
        execution = self._executions.get((submission, run))
        if execution is None:
            return ""
        if not execution.completed:
            status = execution.status.value.replace("_", " ")
            return f"{status} · {execution.error}" if execution.error else status
        text = f"{execution.duration_seconds:.1f} s"
        if item_name is not None:
            output = next((s.output for s in execution.scores if s.name == item_name), None)
            if output:
                text = f"{text} · {output}"
        return text

    def _brush(self, token: str) -> QBrush:
        return QBrush(QColor(self._theme.tokens.color[token]))


class _SubmissionRow:
    """One submission across every test, for the By submission view."""

    def __init__(
        self,
        name: str,
        state: StabilityState,
        affected: list[tuple[ItemStability, SubmissionItemStability]],
        agreed: int,
        changed: int,
        broke: int,
        broke_text: str,
    ) -> None:
        self.name = name
        self.state = state
        self.affected = affected
        self.agreed = agreed
        self.changed = changed
        self.broke = broke
        self.broke_text = broke_text

    @property
    def total(self) -> int:
        return self.agreed + self.changed + self.broke

    @property
    def agreement(self) -> float:
        return self.agreed / self.total if self.total else 0.0

    @classmethod
    def of(cls, report: StabilityReport, submission: SubmissionStability) -> _SubmissionRow:
        affected = [
            (test, entry)
            for test in report.tests
            for entry in test.affected
            if entry.submission == submission.name
        ]
        tests = len(report.tests)
        agreed = sum(entry.runs_agreed for _, entry in affected)
        agreed += (tests - len(affected)) * submission.runs_completed
        broke = submission.runs_broke * tests
        total = submission.runs_total * tests
        parts = []
        if submission.runs_timed_out:
            parts.append(f"timed out ×{submission.runs_timed_out}")
        if submission.runs_crashed:
            parts.append(f"crashed ×{submission.runs_crashed}")
        if submission.runs_broke:
            state = StabilityState.BROKE
        elif affected:
            state = StabilityState.CHANGED
        else:
            state = StabilityState.PASS
        return cls(
            submission.name,
            state,
            affected,
            agreed,
            total - agreed - broke,
            broke,
            " · ".join(parts),
        )


# ----- text helpers -------------------------------------------------------------------------


def _headline(report: StabilityReport) -> str:
    changed = len(report.tests_in(StabilityState.CHANGED))
    broke = len(report.broken_submissions)
    parts = []
    if changed:
        parts.append(f"{changed} test{'' if changed == 1 else 's'} changed result between runs")
    if broke:
        parts.append(
            f"{broke} submission{'' if broke == 1 else 's'} timed out or crashed on some runs"
        )
    if not parts:
        return "Every test gave the same result on every run."
    return ", and ".join(parts).capitalize() + "."


def _meta(report: StabilityReport) -> str:
    parts = [
        report.autograder,
        f"Module {report.module_number}",
        f"{len(report.submissions)} submissions × {report.runs_completed} runs",
    ]
    duration = _duration(report.started_at, report.finished_at)
    if duration:
        parts.append(duration)
    parts.append(f"finished {report.finished_at.replace('T', ' ')}")
    return " · ".join(parts)


def _duration(started: str, finished: str) -> str:
    try:
        delta = datetime.fromisoformat(finished) - datetime.fromisoformat(started)
    except ValueError:
        return ""
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return ""
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} min {rest} s" if minutes else f"{rest} s"


def _points(result: ResultSeen) -> str:
    if result.score is None:
        return "no result"
    if result.max_score is None:
        return f"{result.score:g} pts"
    return f"{result.score:g}/{result.max_score:g} pts"


def _results_seen(entry: SubmissionItemStability) -> str:
    return " · ".join(f"{_points(r)} ×{len(r.runs)}" for r in entry.results)


def _points_seen(criterion: ItemStability) -> str:
    seen: dict[float, None] = {}
    for entry in criterion.affected:
        for result in entry.results:
            if result.score is not None:
                seen.setdefault(result.score, None)
    if not seen:
        return ""
    return " or ".join(f"{score:g}" for score in sorted(seen, reverse=True))


def _total_text(total_range: tuple[float, float] | None, possible: float | None) -> str:
    if total_range is None or possible is None:
        return ""
    low, high = total_range
    span = f"{low:g}" if low == high else f"{low:g} to {high:g}"
    return f"{span} of {possible:g}"


def _tier_note(mapping: ProxyGradeMapping | None, criterion_name: str, prefix: str) -> str:
    if mapping is None:
        return ""
    criterion = next((c for c in mapping.criteria if c.name == criterion_name), None)
    if criterion is None:
        return ""
    notes = []
    for tier in criterion.tiers:
        if prefix in tier.all_of:
            notes.append(f"needed for {tier.points:g}")
        elif prefix in tier.any_of:
            notes.append(f"one of {len(tier.any_of)} for {tier.points:g}")
    return ", ".join(notes)
