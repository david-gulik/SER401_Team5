from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.dtos.stability import StabilityState
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.stability_reports import ReportSummary
from GAVEL.core.active_assignment import AssignmentPick
from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.sanitize.file_manager import show_in_file_manager
from GAVEL.pages.stability_check.results_view import ResultsView
from GAVEL.pages.stability_check.viewmodel import (
    MAX_RUNS,
    MAX_TIMEOUT_MINUTES,
    MIN_RUNS,
    Phase,
    StabilityCheckViewModel,
    StabilityUiState,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing
from GAVEL.ui_components.progress_panel import ProgressPanel
from GAVEL.ui_components.section_card import SectionCard

# The autograder list grows with its rows up to this many, then scrolls. A course
# keeps every autograder version it downloaded, so the list can run long.
AUTOGRADERS_SHOWN = 6


class StabilityCheckTab(ScrollableTab):
    """Set up a check, watch it run, and see what it found."""

    inspect_requested = pyqtSignal(object)  # AssignmentPick: a submission for Inspect Grades

    def __init__(self, theme: ThemeContext, viewmodel: StabilityCheckViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._viewmodel = viewmodel
        self._rendering = False
        self._listed_autograders: list[str] = []
        self._previous_shown: tuple[object, ...] | None = None
        # Swapped out in tests so no question box blocks.
        self.confirm: Callable[[str, str], bool] = self._ask

        self.add_section(self._build_set_up_card())
        self.add_section(self._build_running_card())
        self.add_section(self._build_results_card())
        self.add_stretch()

        viewmodel.state_changed.connect(self._render)
        self._render(viewmodel.state)

    # ----- building ----------------------------------------------------------------------------

    def _build_set_up_card(self) -> QWidget:
        card = SectionCard(self._theme, "Set up")
        self._set_up_card = card

        self.assignment_combo = QComboBox()
        self.assignment_combo.currentIndexChanged.connect(self._on_assignment_changed)

        picker = QWidget()
        picker_layout = QVBoxLayout(picker)
        picker_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(picker_layout, self._theme, 4)
        self.autograder_placeholder = QLabel()
        self.autograder_placeholder.setProperty("role", "text_muted")
        self.autograder_placeholder.setWordWrap(True)
        self.autograder_filter = QLineEdit()
        self.autograder_filter.setPlaceholderText("Filter autograders")
        self.autograder_filter.setClearButtonEnabled(True)
        self.autograder_filter.textChanged.connect(self._apply_autograder_filter)
        self.autograder_list = QListWidget()
        self.autograder_list.setProperty("role", "picker_list")
        self.autograder_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.autograder_list.currentRowChanged.connect(self._on_autograder_picked)
        for widget in (self.autograder_placeholder, self.autograder_filter, self.autograder_list):
            picker_layout.addWidget(widget)

        self.runs_spin = QSpinBox()
        self.runs_spin.setRange(MIN_RUNS, MAX_RUNS)
        self.runs_spin.valueChanged.connect(self._on_runs_changed)

        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 256)
        self.workers_spin.valueChanged.connect(self._on_workers_changed)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, MAX_TIMEOUT_MINUTES)
        self.timeout_spin.setSuffix(" min")
        self.timeout_spin.valueChanged.connect(self._on_timeout_changed)

        form_widget = QWidget()
        self._form_widget = form_widget
        form = QFormLayout(form_widget)
        form.addRow("Assignment", self.assignment_combo)
        form.addRow("Autograder", picker)
        form.addRow("Runs per submission", self.runs_spin)
        form.addRow("Parallel workers", self.workers_spin)
        form.addRow("Timeout per execution", self.timeout_spin)
        card.add_row(form_widget)

        self.estimate_label = QLabel()
        self.estimate_label.setProperty("role", "text_muted")
        self.estimate_label.setWordWrap(True)
        card.add_row(self.estimate_label)

        actions = QWidget()
        self._actions_widget = actions
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(actions_layout, self._theme, 12)
        self.run_button = QPushButton("Run stability check")
        self.run_button.setProperty("role", "primary")
        self.run_button.clicked.connect(self._viewmodel.start)
        self.status_label = QLabel()
        self.status_label.setProperty("role", "text_muted")
        self.status_label.setWordWrap(True)
        actions_layout.addWidget(self.run_button)
        actions_layout.addWidget(self.status_label, 1)
        card.add_row(actions)

        self._previous_widget = QWidget()
        previous_layout = QVBoxLayout(self._previous_widget)
        previous_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(previous_layout, self._theme, 4)
        self.previous_label = QLabel()
        self.previous_label.setProperty("role", "text_muted")
        self.previous_label.setWordWrap(True)
        self.previous_table = QTableWidget(0, 5)
        self.previous_table.setHorizontalHeaderLabels(["Started", "Runs", "Result", "", ""])
        self.previous_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.previous_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.previous_table.verticalHeader().setVisible(False)
        header = self.previous_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        # Sized to the Open and Delete buttons when rows are filled in; fitting to contents
        # would measure the empty cell text and clip the buttons at the table's edge.
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setHighlightSections(False)
        previous_layout.addWidget(self.previous_label)
        previous_layout.addWidget(self.previous_table)
        self._previous_widget.hide()
        card.add_row(self._previous_widget)

        self.change_button = QPushButton("Change")
        self.change_button.setProperty("role", "secondary")
        self.change_button.clicked.connect(self._viewmodel.edit_settings)
        self.change_button.hide()
        # Beside the title, next to the summary it changes, not at the far edge of the card.
        card.add_title_suffix(self.change_button)
        return card

    def _build_running_card(self) -> QWidget:
        card = SectionCard(self._theme, "Checking stability")
        self._running_card = card
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("role", "secondary")
        self.cancel_button.clicked.connect(self._viewmodel.cancel)
        card.add_action(self.cancel_button)
        self.progress_panel = ProgressPanel(self._theme)
        card.add_row(self.progress_panel)
        self.running_note = QLabel("Log lines for each execution go to the terminal.")
        self.running_note.setProperty("role", "text_muted")
        card.add_row(self.running_note)
        card.hide()
        return card

    def _build_results_card(self) -> QWidget:
        card = SectionCard(self._theme, "Results")
        self._results_card = card
        self.run_again_button = QPushButton("Run again")
        self.run_again_button.setProperty("role", "secondary")
        self.run_again_button.clicked.connect(self._viewmodel.start)
        # Beside the title, not at the far edge of the card.
        card.add_title_suffix(self.run_again_button)
        self.results_view = ResultsView(self._theme)
        self.results_view.open_folder_requested.connect(self._open_submission_folder)
        self.results_view.inspect_requested.connect(self._inspect_submission)
        # Swapped out in tests so no file manager window opens.
        self.open_folder = show_in_file_manager
        card.add_row(self.results_view)
        card.hide()
        return card

    def _open_submission_folder(self, name: str) -> None:
        folder = self._viewmodel.submission_folder(name)
        if folder is None:
            self.status_label.setText(f"The folder for {name} is not in the workspace any more.")
            return
        self.open_folder(folder)

    def _inspect_submission(self, name: str) -> None:
        report = self._viewmodel.state.report
        if report is None:
            return
        self.inspect_requested.emit(AssignmentPick(report.course, report.module_number, name))

    def _delete_report(self, summary: ReportSummary) -> None:
        when = summary.started_at.replace("T", " ")[:16]
        if self.confirm(
            "Delete this check?",
            f"Delete the check started {when}?\n\n"
            "Its saved report is removed from the workspace. This cannot be undone.",
        ):
            self._viewmodel.delete_report(summary.path)

    def _ask(self, title: str, text: str) -> bool:
        answer = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    # ----- the page follows the active course ------------------------------------------------

    def set_course(self, course: CourseFolder | None) -> None:
        self._viewmodel.select_course(course)

    # ----- widget events -> viewmodel ---------------------------------------------------------

    def _on_assignment_changed(self, index: int) -> None:
        if self._rendering:
            return
        self._viewmodel.select_module(self.assignment_combo.itemData(index))

    def _on_autograder_picked(self, row: int) -> None:
        if self._rendering:
            return
        item = self.autograder_list.item(row)
        self._viewmodel.select_autograder(
            item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        )

    def _apply_autograder_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for index in range(self.autograder_list.count()):
            item = self.autograder_list.item(index)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_runs_changed(self, value: int) -> None:
        if not self._rendering:
            self._viewmodel.set_runs(value)

    def _on_workers_changed(self, value: int) -> None:
        if not self._rendering:
            self._viewmodel.set_workers(value)

    def _on_timeout_changed(self, value: int) -> None:
        if not self._rendering:
            self._viewmodel.set_timeout_minutes(value)

    # ----- viewmodel -> widgets -----------------------------------------------------------------

    def _render(self, state: object) -> None:
        assert isinstance(state, StabilityUiState)
        self._rendering = True
        try:
            self._render_assignments(state)
            self._render_autograders(state)
            self.runs_spin.setValue(state.runs)
            self.workers_spin.setValue(state.workers)
            self.timeout_spin.setValue(state.timeout_minutes)
            self.estimate_label.setText(state.estimate)
            self._render_previous(state)
            self._render_phase(state)
        finally:
            self._rendering = False

    def _render_assignments(self, state: StabilityUiState) -> None:
        self.assignment_combo.clear()
        self.assignment_combo.addItem("Select an assignment", None)
        for module in state.modules:
            self.assignment_combo.addItem(module.label, module.module_number)
        if state.module is not None:
            self.assignment_combo.setCurrentIndex(
                self.assignment_combo.findData(state.module.module_number)
            )
        self.assignment_combo.setEnabled(bool(state.modules) and state.phase is not Phase.RUNNING)

    def _render_autograders(self, state: StabilityUiState) -> None:
        if state.module is None:
            placeholder = "Pick an assignment to see its autograders."
        elif not state.autograders:
            placeholder = "No autograders for this assignment in the workspace."
        else:
            placeholder = ""
        self.autograder_placeholder.setText(placeholder)
        self.autograder_placeholder.setVisible(bool(placeholder))
        for widget in (self.autograder_filter, self.autograder_list):
            widget.setVisible(not placeholder)
            widget.setEnabled(state.phase is not Phase.RUNNING)

        names = [option.name for option in state.autograders]
        if names != self._listed_autograders:
            # Rebuilt only when the options change, so a state change while the
            # user is typing in the filter does not reset the list under them.
            self._listed_autograders = names
            self.autograder_filter.clear()
            self.autograder_list.clear()
            for option in state.autograders:
                item = QListWidgetItem(option.name)
                item.setData(Qt.ItemDataRole.UserRole, option.name)
                item.setToolTip(str(option.path))
                self.autograder_list.addItem(item)
            self._fit_autograder_list()
        picked = state.autograder.name if state.autograder is not None else None
        self.autograder_list.setCurrentRow(names.index(picked) if picked in names else -1)

    def _fit_autograder_list(self) -> None:
        """As tall as its rows up to AUTOGRADERS_SHOWN of them; the rest scroll."""
        rows = min(self.autograder_list.count(), AUTOGRADERS_SHOWN)
        height = sum(self.autograder_list.sizeHintForRow(index) for index in range(rows))
        self.autograder_list.setFixedHeight(height + 2 * self.autograder_list.frameWidth())

    def _render_previous(self, state: StabilityUiState) -> None:
        running = state.phase is Phase.RUNNING
        shown = (state.autograder, state.previous, state.saved_to, state.phase)
        if shown == self._previous_shown:
            return
        self._previous_shown = shown
        self._previous_widget.setVisible(
            state.autograder is not None and state.phase is not Phase.DONE
        )
        table = self.previous_table
        table.setRowCount(0)
        if state.autograder is None:
            return
        if not state.previous:
            self.previous_label.setText(f"Never checked with {state.autograder.name}.")
            table.hide()
            return
        self.previous_label.setText(f"Previous checks with {state.autograder.name}, newest first.")
        table.show()
        table.setRowCount(len(state.previous))
        open_buttons = []
        delete_buttons = []
        for row, summary in enumerate(state.previous):
            table.setItem(row, 0, QTableWidgetItem(summary.started_at.replace("T", " ")[:16]))
            table.setItem(row, 1, QTableWidgetItem(_runs_text(summary)))
            table.setItem(row, 2, QTableWidgetItem(_outcome_text(summary)))
            on_screen = state.report is not None and summary.path == state.saved_to
            button = QPushButton("Open")
            button.setProperty("role", "secondary")
            if on_screen:
                button.setText("Shown")
                button.setEnabled(False)
            elif running:
                button.setEnabled(False)
            button.clicked.connect(
                lambda _=False, path=summary.path: self._viewmodel.open_report(path)
            )
            table.setCellWidget(row, 3, button)
            open_buttons.append(button)
            delete = QPushButton("Delete")
            delete.setProperty("role", "secondary")
            if on_screen:
                delete.setEnabled(False)
                delete.setToolTip("This check is on screen. Open another one first.")
            elif running:
                delete.setEnabled(False)
            delete.clicked.connect(lambda _=False, s=summary: self._delete_report(s))
            table.setCellWidget(row, 4, delete)
            delete_buttons.append(delete)
        # Room for the widest button plus a margin on each side of it.
        margin = self._theme.tokens.sp(8)
        table.setColumnWidth(3, max(b.sizeHint().width() for b in open_buttons) + 2 * margin)
        table.setColumnWidth(4, max(b.sizeHint().width() for b in delete_buttons) + 2 * margin)
        table.resizeRowsToContents()
        rows = min(table.rowCount(), 6)
        height = table.horizontalHeader().height() + 2 * table.frameWidth()
        height += sum(table.rowHeight(index) for index in range(rows))
        table.setFixedHeight(height)

    def _render_phase(self, state: StabilityUiState) -> None:
        running = state.phase is Phase.RUNNING
        collapsed = state.phase is Phase.DONE
        for widget in (self.runs_spin, self.workers_spin, self.timeout_spin):
            widget.setEnabled(not running)
        self.run_button.setEnabled(state.missing is None and not running)
        self.run_button.setToolTip(state.missing or "")
        self.run_again_button.setEnabled(state.missing is None and not running)
        self.run_again_button.setToolTip(
            state.missing or "Start a new check with the current settings."
        )
        for widget in (self._form_widget, self.estimate_label, self._actions_widget):
            widget.setVisible(not collapsed)
        self.change_button.setVisible(collapsed)
        self._set_up_card.set_subtitle(state.summary if running or collapsed else "")

        if state.course_error:
            self.status_label.setText(state.course_error)
        elif state.phase is Phase.FAILED:
            self.status_label.setText(f"The check failed: {state.error}")
        elif state.missing:
            self.status_label.setText(f"{state.missing} to run a check.")
        else:
            self.status_label.setText("Results are saved to the workspace runs folder.")

        self._running_card.setVisible(running)
        if running:
            self._running_card.set_subtitle(state.summary)
            if state.progress is not None:
                self.progress_panel.show_progress(state.progress)
            self.cancel_button.setEnabled(not state.cancel_requested)
            self.cancel_button.setText("Cancelling…" if state.cancel_requested else "Cancel")
        else:
            self.progress_panel.clear()

        report = state.report
        show_results = report is not None and not running
        self._results_card.setVisible(show_results)
        if show_results:
            if self.results_view.report is not report:
                self.results_view.set_report(report, state.saved_to)
        else:
            self.results_view.clear()


def _runs_text(summary: ReportSummary) -> str:
    if summary.cancelled:
        return f"{summary.runs_completed} of {summary.runs_requested} · cancelled"
    return str(summary.runs_completed)


def _outcome_text(summary: ReportSummary) -> str:
    if summary.verdict is StabilityState.PASS:
        return "Stable"
    changed = f"{_count(summary.tests_changed, 'test')} changed"
    if summary.verdict is StabilityState.CHANGED:
        return changed
    return f"{changed} · {_count(summary.submissions_broke, 'submission')} broke"


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"
