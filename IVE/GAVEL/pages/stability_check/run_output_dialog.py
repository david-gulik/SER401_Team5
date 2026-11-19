"""Everything one autograder run printed, for reading a crash or a timeout in full."""

from __future__ import annotations

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.dtos.stability import ExecutionRecord
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing

NO_OUTPUT = "The autograder printed nothing."


class RunOutputDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        theme: ThemeContext,
        execution: ExecutionRecord,
        autograder: str,
    ) -> None:
        super().__init__(parent)
        self._execution = execution
        self._autograder = autograder
        self.setWindowTitle(f"{execution.submission} · run {execution.run} · output")
        self.setSizeGripEnabled(True)
        self.resize(760, 520)

        self.title_label = QLabel(f"{execution.submission} · run {execution.run}")
        self.title_label.setProperty("role", "h2")
        self.summary_label = QLabel(run_summary(execution, autograder))
        self.summary_label.setProperty("role", "text_muted")
        self.summary_label.setWordWrap(True)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.output.setPlainText(execution.output_tail or NO_OUTPUT)

        self.note_label = QLabel(
            "What the autograder printed to stdout and stderr, as much of the end of it as the "
            "report keeps."
        )
        self.note_label.setProperty("role", "text_muted")
        self.note_label.setWordWrap(True)

        buttons = QHBoxLayout()
        set_spacing(buttons, theme, 8)
        self.copy_button = QPushButton("Copy output")
        self.copy_button.setProperty("role", "secondary")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.close_button = QPushButton("Close")
        self.close_button.setProperty("role", "primary")
        self.close_button.clicked.connect(self.accept)
        buttons.addWidget(self.copy_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)

        root = QVBoxLayout(self)
        set_spacing(root, theme, 8)
        root.addWidget(self.title_label)
        root.addWidget(self.summary_label)
        root.addWidget(self.output, 1)
        root.addWidget(self.note_label)
        root.addLayout(buttons)

    def copy_to_clipboard(self) -> None:
        QApplication.clipboard().setText(run_output_text(self._execution, self._autograder))


def run_summary(execution: ExecutionRecord, autograder: str) -> str:
    status = execution.status.value.replace("_", " ")
    text = f"{status.capitalize()} after {execution.duration_seconds:.1f} s · {autograder}"
    if execution.error:
        text = f"{text}\n{execution.error}"
    return text


def run_output_text(execution: ExecutionRecord, autograder: str) -> str:
    """The dialog's content as plain text, for pasting into a message or an issue."""
    header = f"{execution.submission} · run {execution.run}\n{run_summary(execution, autograder)}"
    return f"{header}\n\n{execution.output_tail or NO_OUTPUT}"
