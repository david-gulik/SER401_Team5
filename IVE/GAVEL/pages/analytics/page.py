from __future__ import annotations

import os
from pathlib import Path

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

        env_dir = (os.getenv("DEFAULT_OUTPUT_DIR") or "").strip()
        workspace_root = (
            Path(env_dir).expanduser() if env_dir else Path.home() / "Downloads" / "GAVEL"
        )

        tab = OverviewTab(self._theme, ctx.services.dataset_readers, workspace_root)

        root = QVBoxLayout(self)
        root.addWidget(tab)


PageRegistry.get().register(
    PageSpec(
        page_id=AnalyticsPage.page_id,
        title=AnalyticsPage.title,
        icon_text="📊",
        factory=lambda ctx: AnalyticsPage(ctx),
        order=15,
        group="General",
    )
)
