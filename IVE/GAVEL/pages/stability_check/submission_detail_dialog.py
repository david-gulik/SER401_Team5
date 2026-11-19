"""Every run of one submission on one test or criterion, grouped by the result it gave."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
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

from GAVEL.app.dtos.stability import ExecutionRecord, StabilityReport, SubmissionItemStability
from GAVEL.pages.stability_check.run_output_dialog import RunOutputDialog, run_output_text
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing

_RUN = Qt.ItemDataRole.UserRole
_RUN_TOOLTIP = "Double-click or right-click for the full output"


class SubmissionDetailDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        theme: ThemeContext,
        report: StabilityReport,
        item_name: str,
        entry: SubmissionItemStability,
        open_folder: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._autograder = report.autograder
        # Swapped out in tests so no second modal dialog blocks.
        self.dialog_launcher: Callable[[QDialog], None] = lambda dialog: dialog.exec()
        self.setWindowTitle(f"{entry.submission} · {item_name}")
        self.setSizeGripEnabled(True)
        self.resize(760, 520)
        executions = {e.run: e for e in report.executions if e.submission == entry.submission}
        self._executions = executions

        self.title_label = QLabel(f"{entry.submission} · {item_name}")
        self.title_label.setProperty("role", "h2")
        usual = entry.usual
        usual_text = f" · usual result {_points(usual.score, usual.max_score)}" if usual else ""
        self.summary_label = QLabel(
            f"{entry.runs_agreed} of {entry.runs_total} runs agreed{usual_text} · "
            f"Module {report.module_number} · {report.autograder}"
        )
        self.summary_label.setProperty("role", "text_muted")
        self.summary_label.setWordWrap(True)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Result", "Time", "Output"])
        # The output column takes what the first two leave; those two can be dragged.
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        for index, result in enumerate(entry.results):
            if result.score is None:
                label = "no result: timed out or crashed"
            elif index == 0:
                label = f"{_points(result.score, result.max_score)} · usual result"
            else:
                label = f"{_points(result.score, result.max_score)} · differs from the usual result"
            group = QTreeWidgetItem([label, f"{len(result.runs)} runs", result.output or ""])
            self.tree.addTopLevelItem(group)
            for run in result.runs:
                row = QTreeWidgetItem(_run_row(run, executions.get(run), item_name))
                row.setData(0, _RUN, run)
                for column in range(3):
                    row.setToolTip(column, _RUN_TOOLTIP)
                group.addChild(row)
            group.setExpanded(True)
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)

        buttons = QHBoxLayout()
        set_spacing(buttons, theme, 8)
        self.open_folder_button = QPushButton("Open submission folder")
        self.open_folder_button.setProperty("role", "secondary")
        if open_folder is None:
            self.open_folder_button.hide()
        else:
            self.open_folder_button.clicked.connect(lambda: open_folder(entry.submission))
        self.close_button = QPushButton("Close")
        self.close_button.setProperty("role", "primary")
        self.close_button.clicked.connect(self.accept)
        buttons.addWidget(self.open_folder_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)

        root = QVBoxLayout(self)
        set_spacing(root, theme, 8)
        root.addWidget(self.title_label)
        root.addWidget(self.summary_label)
        root.addWidget(self.tree, 1)
        root.addLayout(buttons)

    # ----- a run's full output ----------------------------------------------------------------

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        run = item.data(0, _RUN)
        if run is not None:
            self.open_run_output(run)

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.tree.itemAt(pos)
        menu = self.run_menu(item) if item is not None else None
        if menu is not None:
            menu.exec(self.tree.viewport().mapToGlobal(pos))

    def run_menu(self, item: QTreeWidgetItem) -> QMenu | None:
        """The context menu of a run row: view or copy its output. None for a result row."""
        run = item.data(0, _RUN)
        if run is None:
            return None
        menu = QMenu(self.tree)
        view = menu.addAction("View full output…")
        view.triggered.connect(lambda: self.open_run_output(run))
        copy = menu.addAction("Copy output")
        copy.triggered.connect(lambda: self.copy_run_output(run))
        return menu

    def open_run_output(self, run: int) -> None:
        execution = self._executions.get(run)
        if execution is not None:
            self.dialog_launcher(RunOutputDialog(self, self._theme, execution, self._autograder))

    def copy_run_output(self, run: int) -> None:
        execution = self._executions.get(run)
        if execution is not None:
            QApplication.clipboard().setText(run_output_text(execution, self._autograder))


def _points(score: float | None, max_score: float | None) -> str:
    if score is None:
        return "no result"
    if max_score is None:
        return f"{score:g} pts"
    return f"{score:g}/{max_score:g} pts"


def _run_row(run: int, execution: ExecutionRecord | None, item_name: str) -> list[str]:
    if execution is None:
        return [f"Run {run}", "", ""]
    if not execution.completed:
        status = execution.status.value.replace("_", " ")
        return [
            f"Run {run}",
            f"{execution.duration_seconds:.1f} s",
            f"{status} · {execution.error or ''}",
        ]
    output = next((s.output for s in execution.scores if s.name == item_name), None) or ""
    return [f"Run {run}", f"{execution.duration_seconds:.1f} s", output]
