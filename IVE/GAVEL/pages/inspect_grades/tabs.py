from __future__ import annotations

from PyQt6.QtWidgets import QLabel

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard


class InspectGradesTab(ScrollableTab):
    def __init__(self, theme: ThemeContext) -> None:
        super().__init__(theme)

        card = SectionCard(theme, "Inspect Grades")

        message = QLabel("TODO: Grade inspection features")
        message.setProperty("role", "text_muted")

        card.add_row(message)

        self.add_section(card)
        self.add_stretch()
