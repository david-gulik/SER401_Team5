from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import DownloadViewModel


class DownloadPage(BasePage):
    page_id = "download"
    title = "Download"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self._ctx = ctx

        output_dir = Path.home() / "Downloads" / "rosters"
        roster_configured = ctx.services.roster_client is not None

        vm = DownloadViewModel(
            roster_client=ctx.services.roster_client,
            default_output_dir=output_dir,
            logger=ctx.logger,
            roster_configured=roster_configured,
        )

        tab = DownloadTab(ctx.theme, vm)

        root = QVBoxLayout(self)
        root.addWidget(tab)


PageRegistry.get().register(
    PageSpec(
        page_id=DownloadPage.page_id,
        title=DownloadPage.title,
        icon_text="📚",
        factory=lambda ctx: DownloadPage(ctx),
        order=30,
        group="Integrations",
    )
)
