from __future__ import annotations

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.sanitize.viewmodel import SanitizeUiState, SanitizeViewModel
from GAVEL.theme.context import ThemeContext


class SanitizeTab(ScrollableTab):
    """Review consent and anonymize a course's downloaded data."""

    def __init__(self, theme: ThemeContext, vm: SanitizeViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm

        self.add_stretch()

        self._vm.state_changed.connect(self.render)
        self.render(self._vm.get_state())

    def render(self, state: SanitizeUiState) -> None:
        """Paint the widgets from state. The view model is the only source of truth."""
