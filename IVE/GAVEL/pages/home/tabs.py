from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QWidget

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard

_PROJECT_DESCRIPTION = (
    "GAVEL is the Integrated Validation Environment (IVE) for Automated Assessment "
    "Tools. It runs autograders against historical student submissions and compares "
    "the results to human-graded ground truth, helping AAT developers measure accuracy "
    "improvements, catch regressions, and identify scoring instability across "
    "iterations.\n\n"
    "GAVEL offers both an interactive GUI for analysis and a CLI for repeatable, "
    "scalable runs. Use the Download tab to pull course data from Canvas and "
    "Gradescope, and the Settings tab to configure environment variables."
)


class OverviewTab(ScrollableTab):
    def __init__(self, theme: ThemeContext) -> None:
        super().__init__(theme)
        self._theme = theme

        self.add_section(self._build_description_card())
        self.add_stretch()

    def _build_description_card(self) -> QWidget:
        card = SectionCard(self._theme, "About GAVEL")
        description = QLabel(_PROJECT_DESCRIPTION)
        description.setWordWrap(True)
        card.add_row(description)
        return card
