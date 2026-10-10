"""The Anonymize card: run the pipeline on the selected course and show what it wrote."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from GAVEL.app.dtos.course_summary import CourseSummary
from GAVEL.app.usecases.anonymize_course_dataset import AnonymizeCourseDatasetResult
from GAVEL.app.workspace.layout import ANONYMIZED_DIR, GRADEBOOK_FILE, ROSTER_FILE
from GAVEL.pages.sanitize.viewmodel import (
    RunState,
    SanitizeUiState,
    SanitizeViewModel,
    course_label,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing
from GAVEL.ui_components.section_card import SectionCard
from GAVEL.ui_components.sub_panel import SubPanel

RESULT_COLUMNS = ("File", "Kept", "Removed", "Note")
REPLACE_BUTTON_TEXT = "Replace and anonymize"


def _when(course: CourseSummary) -> str:
    moment = course.anonymized_at
    return moment.strftime("%Y-%m-%d %H:%M") if moment else "never"


def replace_warning(course: CourseSummary) -> str:
    return (
        f"{course_label(course.key)} was already anonymized on {_when(course)}. "
        "Anonymizing again deletes its anonymized/ folder and gives every student a new "
        "anonymous ID, so anything built on the old IDs will no longer line up."
    )


def ask_to_replace(parent: QWidget, text: str) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Replace anonymized data?")
    box.setText(text)
    replace = box.addButton(REPLACE_BUTTON_TEXT, QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    box.exec()
    return box.clickedButton() is replace


def run_button_text(state: SanitizeUiState) -> str:
    blocker = state.anonymize_blocker
    if blocker is not None:
        return blocker
    course = state.selected_summary
    verb = "Re-anonymize" if course is not None and course.anonymized_at else "Anonymize"
    count = state.included_count
    return f"{verb} {count} consenting student{'' if count == 1 else 's'}"


def result_rows(
    result: AnonymizeCourseDatasetResult, course: CourseSummary
) -> list[tuple[str, str, str, str]]:
    """``(file, kept, removed, note)`` for each artifact a run wrote or skipped."""
    consent = result.consent_form
    rows = [
        (
            "Consent form",
            str(consent.processed_count),
            str(consent.skipped_count),
            "Rows; every attempt by an included student is kept",
        )
    ]
    for label, path, report in (
        ("Roster", ROSTER_FILE, result.roster),
        ("Gradebook", GRADEBOOK_FILE, result.gradebook),
    ):
        tracked = course.file(path)
        if tracked is None or tracked.original_at is None:
            rows.append((label, "—", "—", "Not in original/, skipped"))
        else:
            removed = report.skipped_count + report.excluded_count
            rows.append((label, str(report.processed_count), str(removed), "Students"))

    rubric_files = sum(
        1 for f in course.files if f.path.startswith("assignments/") and f.original_at
    )
    rubric = result.rubric_assessment
    if rubric_files == 0:
        rows.append(("Rubric assessments", "—", "—", "None in original/"))
    else:
        rows.append(
            (
                "Rubric assessments",
                str(rubric.processed_count),
                str(rubric.skipped_count + rubric.excluded_count),
                f"Assessments across {rubric_files} file{'' if rubric_files == 1 else 's'}",
            )
        )
    return rows


class AnonymizeCard(SectionCard):
    def __init__(
        self,
        theme: ThemeContext,
        vm: SanitizeViewModel,
        open_location: Callable[[Path], None],
        confirm_replace: Callable[[QWidget, str], bool] = ask_to_replace,
    ) -> None:
        super().__init__(theme, "Anonymize")
        self._theme = theme
        self._vm = vm
        self._open_location = open_location
        self._confirm_replace = confirm_replace
        self._output_path: Path | None = None

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(output_layout, theme, 8)
        output_key = QLabel("Output")
        output_key.setProperty("role", "text_muted")
        self._output_label = QLabel()
        self._output_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # Long paths are cut off instead of widening the page; the tooltip has all of it.
        self._output_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._open_btn = QPushButton("Open folder")
        self._open_btn.setProperty("role", "secondary")
        self._open_btn.clicked.connect(self._open_output)
        output_layout.addWidget(output_key)
        output_layout.addWidget(self._output_label, 1)
        output_layout.addWidget(self._open_btn)

        self._run_btn = QPushButton()
        self._run_btn.setProperty("role", "primary")
        self._run_btn.setMinimumHeight(theme.tokens.sp(32))
        self._run_btn.clicked.connect(self._on_run_clicked)

        self._results = SubPanel(theme, "Results")
        self._results_status = QLabel()
        self._results_status.setProperty("role", "text_muted")
        self._results_status.setWordWrap(True)
        self._results_grid_host = QWidget()
        self._results_grid = QGridLayout(self._results_grid_host)
        self._results_grid.setContentsMargins(0, 0, 0, 0)
        self._results_grid.setHorizontalSpacing(theme.tokens.sp(24))
        self._results_grid.setVerticalSpacing(theme.tokens.sp(4))
        self._results_grid.setColumnStretch(3, 1)
        self._results.add_widget(self._results_status)
        self._results.add_widget(self._results_grid_host)

        for widget in (output_row, self._run_btn, self._results):
            self.add_row(widget)

    @property
    def run_button(self) -> QPushButton:
        return self._run_btn

    @property
    def open_button(self) -> QPushButton:
        return self._open_btn

    @property
    def output_label(self) -> QLabel:
        return self._output_label

    @property
    def results_status(self) -> QLabel:
        return self._results_status

    def result_texts(self) -> list[list[str]]:
        """The results grid as text, one list per row, header row first."""
        grid = self._results_grid
        rows = []
        for row in range(grid.rowCount()):
            cells = []
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                widget = item.widget() if item is not None else None
                if isinstance(widget, QLabel):
                    cells.append(widget.text())
            if cells:
                rows.append(cells)
        return rows

    def render(self, state: SanitizeUiState) -> None:
        course = state.selected_summary
        self._output_path = course.path / ANONYMIZED_DIR if course else None
        output_text = str(self._output_path) if self._output_path else "—"
        self._output_label.setText(output_text)
        self._output_label.setToolTip(output_text if self._output_path else "")
        self._open_btn.setEnabled(bool(self._output_path and self._output_path.is_dir()))

        self._run_btn.setText(run_button_text(state))
        self._run_btn.setEnabled(state.anonymize_blocker is None)

        run_state = state.selected_run_state
        result = state.run_result if run_state is RunState.SUCCEEDED else None
        if course is None:
            status = "Select a course to anonymize."
        elif run_state is RunState.RUNNING:
            status = "Running…"
        elif run_state is RunState.FAILED:
            status = f"The run failed: {state.run_error}"
        elif result is not None:
            status = "From the run just now. Open folder shows what was written."
        elif course.anonymized_at:
            status = (
                f"Last anonymized {_when(course)}. Results from that run are not kept; "
                "anonymize again to see them."
            )
        else:
            status = "No results yet. Anonymize to see what was written."
        self._results_status.setText(status)
        self._fill_results(result_rows(result, course) if result is not None and course else [])

    def _fill_results(self, rows: list[tuple[str, str, str, str]]) -> None:
        while self._results_grid.count():
            item = self._results_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._results_grid_host.setVisible(bool(rows))
        if not rows:
            return
        for column, title in enumerate(RESULT_COLUMNS):
            header = QLabel(title.upper())
            header.setProperty("role", "readout_key")
            self._results_grid.addWidget(header, 0, column)
        for row, values in enumerate(rows, start=1):
            for column, text in enumerate(values):
                cell = QLabel(text)
                cell.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                if column == 3 or text == "—":
                    cell.setProperty("role", "text_muted")
                self._results_grid.addWidget(cell, row, column)

    def _on_run_clicked(self) -> None:
        state = self._vm.get_state()
        course = state.selected_summary
        if course is None or state.anonymize_blocker is not None:
            return
        if course.anonymized_at is not None and not self._confirm_replace(
            self, replace_warning(course)
        ):
            return
        self._vm.anonymize()

    def _open_output(self) -> None:
        if self._output_path is not None and self._output_path.is_dir():
            self._open_location(self._output_path)
