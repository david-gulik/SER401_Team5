from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.sanitize.tabs import SanitizeTab
from GAVEL.pages.sanitize.viewmodel import SanitizeViewModel

_ICONS_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"


class SanitizePage(BasePage):
    page_id = "sanitize"
    title = "Sanitize"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self._ctx = ctx

        vm = SanitizeViewModel()
        self._tab = SanitizeTab(ctx.theme, vm)

        root = QVBoxLayout(self)
        root.addWidget(self._tab)


PageRegistry.get().register(
    PageSpec(
        page_id=SanitizePage.page_id,
        title=SanitizePage.title,
        icon_text="🛡",
        factory=lambda ctx: SanitizePage(ctx),
        order=40,
        group="Integrations",
        icon_path=_ICONS_DIR / "sanitize.svg",
    )
)
