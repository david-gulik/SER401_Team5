"""Interactive preview for InputModeToggle with the real GAVEL theme.

Not collected by pytest (no test_ prefix). Run from the IVE folder:
    python -m tests.manual.preview_input_mode_toggle

Nothing here touches the network. "Load" buttons populate fake lists after a
short delay so the busy state is visible. The log at the bottom prints every
value_changed / mode_changed emission so you can see exactly what a view
model would receive.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from GAVEL.theme.context import ThemeContext
from GAVEL.theme.qss_builder import build_app_qss
from GAVEL.theme.tokens import load_tokens
from GAVEL.ui_components.input_mode_toggle import ComboPicker, InputModeToggle
from GAVEL.ui_components.section_card import SectionCard

FAKE_TERMS = [
    ("2267", "2267  Fall 2026"),
    ("2271", "2271  Spring 2027"),
    ("2261", "2261  Spring 2026"),
]
FAKE_COURSES = [
    ("213877", "SER401  Capstone I"),
    ("209555", "SER334  Operating Systems"),
    ("201234", "SER222  Data Structures"),
]


def term_code(text: str) -> str | None:
    if len(text) == 4 and text.isdigit() and text[0] == "2" and text[-1] in "1479":
        return None
    return "Term codes look like 2267: 2, two-digit year, then 1/4/7/9 for the semester."


def digits_only(text: str) -> str | None:
    return None if text.isdigit() else "Course IDs are numbers only."


class Preview(QWidget):
    def __init__(self, theme: ThemeContext) -> None:
        super().__init__()
        self.setWindowTitle("InputModeToggle preview")
        self._theme = theme

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(200)

        self._term = self._build_term()
        self._course = self._build_course()

        card = SectionCard(theme, "myASU Class Roster / Canvas")
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self._term)
        row_layout.addWidget(self._course)
        card.add_row(row)

        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        busy = QCheckBox("Simulate busy (download in progress)")
        busy.toggled.connect(self._on_busy)
        token = QCheckBox("Canvas token available")
        token.setChecked(True)
        token.toggled.connect(self._on_token)
        controls_layout.addWidget(busy)
        controls_layout.addWidget(token)
        controls_layout.addStretch(1)

        page = QFrame()
        page.setProperty("role", "app_bg")
        page_layout = QVBoxLayout(page)
        page_layout.addWidget(card)
        page_layout.addWidget(controls)
        page_layout.addWidget(self._log, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self._log_line(
            f"ready. term value={self._term.value()!r} course value={self._course.value()!r}"
        )

    # ---------- builders ----------

    def _build_term(self) -> InputModeToggle:
        picker = ComboPicker(self._theme, load_text="Load Terms", empty_text="No terms loaded")
        toggle = InputModeToggle(
            self._theme,
            "Term",
            picker=picker,
            manual_field_label="Term code",
            picker_label="Choose from list",
            manual_label="Enter code",
            picker_hint="Press Load Terms to fetch the term list from myASU.",
            manual_hint="Format 2[YY][T]. T is 1 Spring, 4 Summer, 7 Fall, 9 Winter.",
            manual_placeholder="e.g. 2267",
            validator=term_code,
        )
        picker.load_requested.connect(lambda: self._fake_load(toggle, FAKE_TERMS, "2267"))
        self._wire_log(toggle, "term")
        return toggle

    def _build_course(self) -> InputModeToggle:
        picker = ComboPicker(self._theme, load_text="Reload", empty_text="No courses loaded")
        toggle = InputModeToggle(
            self._theme,
            "Course",
            picker=picker,
            manual_field_label="Course ID",
            picker_label="Choose from list",
            manual_label="Enter ID",
            picker_hint="Courses load from Canvas when the tab opens.",
            manual_placeholder="e.g. 213877",
            validator=digits_only,
        )
        picker.load_requested.connect(lambda: self._fake_load(toggle, FAKE_COURSES))
        self._wire_log(toggle, "course")
        QTimer.singleShot(400, lambda: self._fake_load(toggle, FAKE_COURSES))
        return toggle

    # ---------- behaviour ----------

    def _fake_load(self, toggle: InputModeToggle, items, select: str = "") -> None:
        toggle.set_busy(True)
        self._log_line("loading…")

        def done() -> None:
            toggle.set_busy(False)
            picker = toggle.picker()
            assert isinstance(picker, ComboPicker)
            picker.set_items(items, select=select)
            self._log_line(f"loaded {len(items)} items")

        QTimer.singleShot(700, done)

    def _wire_log(self, toggle: InputModeToggle, name: str) -> None:
        toggle.value_changed.connect(lambda v: self._log_line(f"{name}.value_changed({v!r})"))
        toggle.mode_changed.connect(
            lambda m: self._log_line(
                f"{name}.mode_changed({m.name}) readout={toggle.readout_text()!r}"
            )
        )

    def _on_busy(self, on: bool) -> None:
        self._term.set_busy(on)
        self._course.set_busy(on)
        self._log_line(f"busy={on}")

    def _on_token(self, on: bool) -> None:
        self._course.set_picker_available(
            on, "Course list needs CANVAS_TOKEN in .env. Enter the course ID directly."
        )
        self._log_line(f"canvas token available={on} -> course mode={self._course.mode().name}")

    def _log_line(self, text: str) -> None:
        self._log.appendPlainText(text)


def main() -> None:
    app = QApplication(sys.argv)
    tokens = load_tokens(
        Path(__file__).resolve().parents[2] / "GAVEL" / "theme" / "tokens_dark.json"
    )
    app.setStyleSheet(build_app_qss(tokens))
    window = Preview(ThemeContext(tokens=tokens))
    window.resize(1000, 640)
    window.show()
    if "--smoke" in sys.argv:
        QTimer.singleShot(1500, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
