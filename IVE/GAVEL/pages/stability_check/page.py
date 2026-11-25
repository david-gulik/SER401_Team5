from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.stability_check.tabs import StabilityCheckTab
from GAVEL.pages.stability_check.viewmodel import StabilityCheckViewModel

_ICONS_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"
# The page a submission is handed to; it reads ctx.active_assignment when it opens.
INSPECT_GRADES_PAGE_ID = "inspect_grades"


class StabilityCheckPage(BasePage):
    page_id = "stability_check"
    title = "Stability Check"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()

        viewmodel = StabilityCheckViewModel(
            dataset_readers=ctx.services.dataset_readers,
            workspace=ctx.active_course.workspace,
            runner=ctx.services.autograder_runner,
        )

        tab = StabilityCheckTab(ctx.theme, viewmodel)
        # Pages are built the first time they open, so read the current pick as well.
        ctx.active_course.changed.connect(tab.set_course)
        tab.set_course(ctx.active_course.course)
        tab.inspect_requested.connect(
            lambda pick: ctx.active_assignment.hand_off(pick, INSPECT_GRADES_PAGE_ID)
        )

        root = QVBoxLayout(self)
        root.addWidget(tab)


PageRegistry.get().register(
    PageSpec(
        page_id=StabilityCheckPage.page_id,
        title=StabilityCheckPage.title,
        icon_text="~",
        factory=lambda ctx: StabilityCheckPage(ctx),
        order=45,
        group="Verification",
        icon_path=_ICONS_DIR / "stability.svg",
        uses_active_course=True,
    )
)
