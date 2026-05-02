from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.home.tabs import OverviewTab

_ICONS_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"


class HomePage(BasePage):
    page_id = "home"
    title = "Home"

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
        page_id=HomePage.page_id,
        title=HomePage.title,
        icon_text="🏠",
        factory=lambda ctx: HomePage(ctx),
        order=10,
        group="General",
        icon_path=_ICONS_DIR / "home.svg",
    )
)
