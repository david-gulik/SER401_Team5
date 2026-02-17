from __future__ import annotations

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.home.tabs import DataEntryTab, OverviewTab
from GAVEL.pages.home.viewmodel import HomeViewModel


class HomePage(BasePage):
    page_id = "home"
    title = "Home"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self._theme = ctx.theme

        # Page-scoped VM, shared across tabs
        self._vm = HomeViewModel(ctx.config, ctx.logger)

        self._tabs = QTabWidget()
        for tab_title, tab_widget in self.build_tabs():
            self._tabs.addTab(tab_widget, tab_title)

        root = QVBoxLayout(self)
        root.addWidget(self._tabs)

    def build_tabs(self):
        return [
            ("Overview", OverviewTab(self._theme, self._vm)),
            ("Data Entry", DataEntryTab(self._theme, self._vm)),
        ]


PageRegistry.get().register(
    PageSpec(
        page_id=HomePage.page_id,
        title=HomePage.title,
        icon_text="🏠",
        factory=lambda ctx: HomePage(ctx),
        order=10,
        group="General",
    )
)
