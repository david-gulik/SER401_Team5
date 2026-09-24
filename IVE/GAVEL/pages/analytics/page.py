from __future__ import annotations

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.analytics.tabs import OverviewTab


class AnalyticsPage(BasePage):
    page_id = "analytics"
    title = "Analytics"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self._theme = ctx.theme

        self._tabs = QTabWidget()
        for tab_title, tab_widget in self.build_tabs():
            self._tabs.addTab(tab_widget, tab_title)

        root = QVBoxLayout(self)
        root.addWidget(self._tabs)

    def build_tabs(self):
        return [
            ("Overview", OverviewTab(self._theme)),
        ]


PageRegistry.get().register(
    PageSpec(
        page_id=AnalyticsPage.page_id,
        title=AnalyticsPage.title,
        icon_text="📊",
        factory=lambda ctx: AnalyticsPage(ctx),
        order=40,
        group="Analytics",
    )
)
