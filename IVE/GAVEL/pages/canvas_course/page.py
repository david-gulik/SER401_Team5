from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout

from GAVEL.app_context import AppContext
from GAVEL.core.base_page import BasePage
from GAVEL.core.page_registry import PageRegistry, PageSpec
from GAVEL.pages.canvas_course.tabs import CanvasCourseTab
from GAVEL.pages.canvas_course.viewmodel import CanvasCourseViewModel


class CanvasCoursePage(BasePage):
    page_id = "canvas_course"
    title = "Canvas Course"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self._ctx = ctx

        default_output_dir = Path.home() / "Downloads" / "canvas_courses"
        canvas_cfg = ctx.config.get().canvas
        canvas_configured = bool(canvas_cfg.base_url and canvas_cfg.token)

        vm = CanvasCourseViewModel(
            use_case=ctx.services.download_course_data_uc,
            default_output_dir=default_output_dir,
            logger=ctx.logger,
            canvas_configured=canvas_configured,
        )

        tab = CanvasCourseTab(ctx.theme, vm)

        self._tabs = QTabWidget()
        self._tabs.addTab(tab, "Download")

        root = QVBoxLayout(self)
        root.addWidget(self._tabs)


PageRegistry.get().register(
    PageSpec(
        page_id=CanvasCoursePage.page_id,
        title=CanvasCoursePage.title,
        icon_text="📚",
        factory=lambda ctx: CanvasCoursePage(ctx),
        order=30,
        group="Integrations",
    )
)
