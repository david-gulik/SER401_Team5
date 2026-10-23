from __future__ import annotations

from PyQt6.QtWidgets import QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.inspect_grades.tabs import InspectGradesTab


class InspectGradesPage(BasePage):
    page_id = "inspect_grades"
    title = "Inspect Grades"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()

        tab = InspectGradesTab(ctx.theme)

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
