from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.autograders.tabs import AutogradersDiagnosticsPage, RunAutogradersTab

_ICONS_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"


class AutogradersPage(BasePage):
    page_id = "autograders"
    title = "Autograders"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self._ctx = ctx
        self._theme = ctx.theme
        self._tabs = QTabWidget()
        for tab_title, tab_widget in self.build_tabs():
            self._tabs.addTab(tab_widget, tab_title)

        root = QVBoxLayout(self)
        root.addWidget(self._tabs)

    def build_tabs(self):
        return [
            ("Run Autograder(s)", RunAutogradersTab(self._theme)),
            ("Autograder Diagnostics", AutogradersDiagnosticsPage(self._theme)),
        ]


PageRegistry.get().register(
    PageSpec(
        page_id=AutogradersPage.page_id,
        title=AutogradersPage.title,
        icon_text="⏵",
        factory=lambda ctx: AutogradersPage(ctx),
        order=40,
        group="Verification",
        icon_path=_ICONS_DIR / "autograders.svg",
        uses_active_course=True,
    )
)
