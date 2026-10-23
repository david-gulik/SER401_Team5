
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtWidgets import QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.inspect_grades.tabs import InspectGradesTab
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel


class InspectGradesPage(BasePage):
    page_id = "inspect_grades"
    title = "Inspect Grades"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()

        env_dir = (os.getenv("DEFAULT_OUTPUT_DIR") or "").strip()
        workspace_root = (
            Path(env_dir).expanduser()
            if env_dir
            else Path.home() / "Downloads" / "GAVEL"
        )

        viewmodel = InspectGradesViewModel(
            workspace_root=workspace_root,
            dataset_readers=ctx.services.dataset_readers,
        )

        tab = InspectGradesTab(ctx.theme, viewmodel)

        root = QVBoxLayout(self)
        root.addWidget(tab)


PageRegistry.get().register(
    PageSpec(
        page_id=InspectGradesPage.page_id,
        title=InspectGradesPage.title,
        icon_text="📋",
        factory=lambda ctx: InspectGradesPage(ctx),
        order=50,
        group="Analytics",
    )
)
