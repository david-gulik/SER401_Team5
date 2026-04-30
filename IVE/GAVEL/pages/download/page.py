from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtWidgets import QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import DownloadViewModel

_ICONS_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"


class DownloadPage(BasePage):
    page_id = "download"
    title = "Download"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self._ctx = ctx

        env_dir = (os.getenv("DEFAULT_OUTPUT_DIR") or "").strip()
        output_dir = Path(env_dir).expanduser() if env_dir else Path.home() / "Downloads" / "GAVEL"
        roster_configured = ctx.services.roster_client is not None

        vm = DownloadViewModel(
            roster_client=ctx.services.roster_client,
            canvas_client=ctx.services.canvas_client,
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
        icon_path=_ICONS_DIR / "home.svg",
    )
)
