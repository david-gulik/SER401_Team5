"""The results of a stability check: a verdict band and a tree from test down to run."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.dtos.stability import (
    ExecutionRecord,
    ItemStability,
    ResultSeen,
    StabilityReport,
    StabilityState,
    SubmissionItemStability,
    SubmissionStability,
)
from GAVEL.pages.stability_check.agreement_bar import AgreementCell
from GAVEL.pages.stability_check.run_output_dialog import RunOutputDialog, run_output_text
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing

RUNS_SHOWN_AT_FIRST = 4
_SHOW_MORE = "show-more"
_ROLE = Qt.ItemDataRole.UserRole
_PAYLOAD = Qt.ItemDataRole.UserRole + 1
_RUN_TOOLTIP = "Double-click or right-click for the full output"


class SortOrder(Enum):
    WORST_FIRST = "Worst first"
    MOST_AFFECTED = "Most submissions affected"
    NAME = "Test name"


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
_GROUP_NOTE = {
    StabilityState.BROKE: "the autograder timed out or crashed on at least one run",
    StabilityState.CHANGED: "the same submission scored differently on different runs",
    StabilityState.PASS: "the same result on every completed run for every submission",
}

FOOTNOTE = (
    "Broke: the autograder timed out or crashed on at least one run. Changed: the same "
    "submission scored differently on different runs. Stable: the same result on every "
    "completed run for every submission. Runs agreed counts every execution that matched the "
    "submission's usual result for that test; a run with no result counts against it. The tree "
    "is test, then submission, then one row per distinct result, then the runs that gave it. "
    "Double-click or right-click a run for everything the autograder printed."
)


class ResultsView(QWidget):
    def __init__(self, theme: ThemeContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._report: StabilityReport | None = None
        self._executions: dict[tuple[str, int], ExecutionRecord] = {}
        # Swapped out in tests so no modal dialog blocks.
        self.dialog_launcher: Callable[[QDialog], None] = lambda dialog: dialog.exec()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        set_spacing(root, theme, 12)
        root.addWidget(self._build_band())
        root.addWidget(self._build_controls())
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Test", "Runs agreed", "Submissions"])
        # The first column takes what the others leave; the others can be dragged.
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(1, 240)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
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
        controls = QWidget()
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(layout, self._theme, 12)
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
        self.sort_combo.currentIndexChanged.connect(lambda _: self._rebuild())
        self.show_stable_check = QCheckBox("Show stable tests")
        self.show_stable_check.toggled.connect(lambda _: self._rebuild())
        layout.addWidget(sort_label)
        layout.addWidget(self.sort_combo)
        layout.addWidget(self.show_stable_check)
        layout.addStretch(1)
        return controls

    # ----- showing a report --------------------------------------------------------------------

    @property
    def report(self) -> StabilityReport | None:
        return self._report

    @property
    def sort_order(self) -> SortOrder:
        return self.sort_combo.currentData()

    def set_report(self, report: StabilityReport, saved_to: Path | None = None) -> None:
        self._report = report
        self._executions = {(e.submission, e.run): e for e in report.executions}
        self._render_band(report)
        self.saved_label.setText(f"Saved to {saved_to}" if saved_to else "")
        self._rebuild()

    def clear(self) -> None:
        self._report = None
        self._executions = {}
        self.tree.clear()
        self.saved_label.clear()

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

    def _rebuild(self) -> None:
        self.tree.clear()
        report = self._report
        if report is None:
            return
        if report.broken_submissions:
            group = self._group(StabilityState.BROKE, len(report.broken_submissions), "submissions")
            for submission in report.broken_submissions:
                self._add_broken_submission(group, submission)
            group.setExpanded(True)

        for state in (StabilityState.CHANGED, StabilityState.PASS):
            tests = report.tests_in(state)
            if not tests:
                continue
            show = state is not StabilityState.PASS or self.show_stable_check.isChecked()
            group = self._group(state, len(tests), "tests", listed=show)
            if not show:
                continue
            for test in self._sorted(tests):
                self._add_test(group, test)
            group.setExpanded(True)
        self.tree.resizeColumnToContents(2)

    def _group(
        self, state: StabilityState, count: int, noun: str, listed: bool = True
    ) -> QTreeWidgetItem:
        label = {
            StabilityState.BROKE: "Broke",
            StabilityState.CHANGED: "Changed",
            StabilityState.PASS: "Stable",
        }[state]
        noun = noun[:-1] if count == 1 else noun
        text = f"{label} · {count} {noun}"
        if not listed:
            text += " · tick Show stable tests to list them"
        item = QTreeWidgetItem([text, "", ""])
        # The definition lives in the tooltip and the footnote, so the row stays short.
        item.setToolTip(0, f"{label}: {_GROUP_NOTE[state]}.")
        item.setFirstColumnSpanned(True)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = QFont()
        font.setBold(True)
        item.setFont(0, font)
        item.setForeground(0, _color(self._theme, _DOT[state]))
        item.setData(0, _ROLE, state.value)
        self.tree.addTopLevelItem(item)
        return item

    def _sorted(self, tests: tuple[ItemStability, ...]) -> list[ItemStability]:
        order = self.sort_order
        if order is SortOrder.NAME:
            return sorted(tests, key=lambda t: t.name.lower())
        if order is SortOrder.MOST_AFFECTED:
            return sorted(tests, key=lambda t: (-t.submissions_affected, t.agreement, t.name))
        return sorted(tests, key=lambda t: (t.agreement, -t.runs_broke, t.name))

    def _add_test(self, group: QTreeWidgetItem, test: ItemStability) -> None:
        item = QTreeWidgetItem(
            [test.name, "", f"{test.submissions_affected} of {test.submissions_total}"]
        )
        item.setData(0, _ROLE, "test")
        item.setForeground(0, _color(self._theme, _DOT[test.state]))
        group.addChild(item)
        self.tree.setItemWidget(
            item,
            1,
            AgreementCell(
                self._theme,
                test.runs_agreed,
                test.runs_changed,
                test.runs_broke,
                f"{round(test.agreement * 100)}% · {test.runs_agreed}/{test.runs_total}",
            ),
        )
        for entry in test.affected:
            self._add_submission(item, entry, test.name)

    def _add_submission(
        self, parent: QTreeWidgetItem, entry: SubmissionItemStability, test_name: str
    ) -> None:
        item = QTreeWidgetItem([entry.submission, "", _results_seen(entry)])
        item.setData(0, _ROLE, "submission")
        parent.addChild(item)
        self.tree.setItemWidget(
            item,
            1,
            AgreementCell(
                self._theme,
                entry.runs_agreed,
                entry.runs_total - entry.runs_agreed - entry.runs_broke,
                entry.runs_broke,
                f"{entry.runs_agreed}/{entry.runs_total}",
            ),
        )
        for index, result in enumerate(entry.results):
            self._add_result(item, result, entry.submission, test_name, usual=index == 0)

    def _add_result(
        self,
        parent: QTreeWidgetItem,
        result: ResultSeen,
        submission: str,
        test_name: str,
        usual: bool,
    ) -> None:
        count = len(result.runs)
        note = "usual result" if usual and result.score is not None else ""
        if result.score is None:
            note = "no result: timed out or crashed"
        elif not usual:
            note = "differs from the usual result"
        text = _points(result)
        if result.output:
            note = f"{note} · output: {result.output}" if note else f"output: {result.output}"
        item = QTreeWidgetItem([f"{text} · {note}" if note else text, "", f"{count} runs"])
        item.setData(0, _ROLE, "result")
        parent.addChild(item)
        self._add_runs(
            item, submission, result.runs, lambda run: self._run_text(submission, run, test_name)
        )

    def _add_broken_submission(
        self, group: QTreeWidgetItem, submission: SubmissionStability
    ) -> None:
        parts = []
        if submission.runs_timed_out:
            parts.append(f"timed out ×{submission.runs_timed_out}")
        if submission.runs_crashed:
            parts.append(f"crashed ×{submission.runs_crashed}")
        item = QTreeWidgetItem([submission.name, "", " · ".join(parts)])
        item.setData(0, _ROLE, "submission")
        group.addChild(item)
        self.tree.setItemWidget(
            item,
            1,
            AgreementCell(
                self._theme,
                submission.runs_completed,
                0,
                submission.runs_broke,
                f"{submission.runs_completed}/{submission.runs_total}",
            ),
        )
        runs = tuple(
            e.run
            for e in sorted(self._executions.values(), key=lambda e: e.run)
            if e.submission == submission.name and not e.completed
        )
        self._add_runs(
            item, submission.name, runs, lambda run: self._run_text(submission.name, run, None)
        )

    def _add_runs(
        self, parent: QTreeWidgetItem, submission: str, runs: tuple[int, ...], text_of
    ) -> None:
        for index, run in enumerate(runs):
            item = QTreeWidgetItem([f"Run {run}", "", text_of(run)])
            item.setData(0, _ROLE, "run")
            item.setData(0, _PAYLOAD, (submission, run))
            for column in range(3):
                item.setToolTip(column, _RUN_TOOLTIP)
            parent.addChild(item)
            if index >= RUNS_SHOWN_AT_FIRST:
                item.setHidden(True)
        hidden = len(runs) - RUNS_SHOWN_AT_FIRST
        if hidden > 0:
            more = QTreeWidgetItem([f"Show {hidden} more runs", "", ""])
            more.setData(0, _ROLE, _SHOW_MORE)
            more.setForeground(0, _color(self._theme, "text_link"))
            parent.addChild(more)

    def _run_text(self, submission: str, run: int, test_name: str | None) -> str:
        execution = self._executions.get((submission, run))
        if execution is None:
            return ""
        if not execution.completed:
            status = execution.status.value.replace("_", " ")
            return f"{status} · {execution.error}" if execution.error else status
        text = f"{execution.duration_seconds:.1f} s"
        if test_name is not None:
            output = next((s.output for s in execution.scores if s.name == test_name), None)
            if output:
                text = f"{text} · {output}"
        return text

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if item.data(0, _ROLE) != _SHOW_MORE:
            return
        parent = item.parent()
        if parent is None:
            return
        for index in range(parent.childCount()):
            parent.child(index).setHidden(False)
        parent.removeChild(item)

    # ----- a run's full output ----------------------------------------------------------------

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if item.data(0, _ROLE) == "run":
            self.open_run_output(*item.data(0, _PAYLOAD))

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.tree.itemAt(pos)
        menu = self.run_menu(item) if item is not None else None
        if menu is not None:
            menu.exec(self.tree.viewport().mapToGlobal(pos))

    def run_menu(self, item: QTreeWidgetItem) -> QMenu | None:
        """The context menu of a run row: view or copy its output. None for any other row."""
        if item.data(0, _ROLE) != "run":
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
        seconds = int(
            (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
        )
    except ValueError:
        return ""
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


def _color(theme: ThemeContext, token: str):
    from PyQt6.QtGui import QBrush, QColor

    return QBrush(QColor(theme.tokens.color[token]))
