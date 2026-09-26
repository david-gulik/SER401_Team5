from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.chart_canvas import ChartCanvas
from GAVEL.ui_components.section_card import SectionCard

_EMPTY_STATE_TEXT = (
    "No analytics charts have been added yet. Individual charts, such as the "
    "human vs autograder heat map, are added to this page as their own tickets."
)


class OverviewTab(ScrollableTab):
    def __init__(self, theme: ThemeContext) -> None:
        super().__init__(theme)
        self._theme = theme

        self.add_section(self._build_placeholder_card())
        self.add_stretch()

    def _build_placeholder_card(self) -> QWidget:
        card = SectionCard(self._theme, "Analytics")
        canvas = ChartCanvas(self._theme, placeholder_text=_EMPTY_STATE_TEXT)
        card.add_row(canvas)
        return card
