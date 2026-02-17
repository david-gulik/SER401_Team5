from __future__ import annotations

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.settings.tabs import AboutTab, PreferencesTab
from GAVEL.pages.settings.viewmodel import SettingsViewModel


class SettingsPage(BasePage):
    page_id = "settings"
    title = "Settings"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self._theme = ctx.theme

        # Page-scoped VM, shared across settings tabs
        self._vm = SettingsViewModel(ctx.config, ctx.logger)

        self._tabs = QTabWidget()
        for tab_title, tab_widget in self.build_tabs():
            self._tabs.addTab(tab_widget, tab_title)

        root = QVBoxLayout(self)
        root.addWidget(self._tabs)

    def build_tabs(self):
        return [
            ("Preferences", PreferencesTab(self._theme, self._vm)),
            ("About", AboutTab(self._theme, self._vm)),
        ]


PageRegistry.get().register(
    PageSpec(
        page_id=SettingsPage.page_id,
        title=SettingsPage.title,
        icon_text="⚙️",
        factory=lambda ctx: SettingsPage(ctx),
        order=20,
        group="General",
    )
)
