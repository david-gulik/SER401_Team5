from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout

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

        tab = OverviewTab(self._theme)

        root = QVBoxLayout(self)
        root.addWidget(tab)


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
