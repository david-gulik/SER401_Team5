from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFrame, QHBoxLayout

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard


class RunAutogradersTab(ScrollableTab):
    def __init__(self, theme: ThemeContext) -> None:
        super().__init__(theme)
        self._theme = theme

        self.add_section(self._build_description_card())
        self.add_stretch()

    def _build_description_card(self) -> QWidget:
        card = SectionCard(self._theme, "Run Autograder(s)")
        description = QLabel("This is just a stub right now...")
        description.setWordWrap(True)
        card.add_row(description)
        return card

class AutogradersDiagnosticsPage(ScrollableTab):
    def __init__(self, theme: ThemeContext) -> None:
        super().__init__(theme)
        self._theme = theme

        self.add_section(self._build_description_card())
        self.add_stretch()

    def _build_description_card(self) -> QWidget:
        card = SectionCard(self._theme, "Autograders Diagnostics")
        description = QLabel("This is just a stub right now...")
        description.setWordWrap(True)
        card.add_row(description)
        return card
