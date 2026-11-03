from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QStatusBar, QWidget

from GAVEL.app_context import AppContext
from GAVEL.core.course_selector import ActiveCourseChip, ActiveCourseGate
from GAVEL.core.navigation_drawer import NavigationDrawer
from GAVEL.core.page_registry import PageRegistry, PageSpec


class MainWindow(QMainWindow):
    def __init__(self, registry: PageRegistry, ctx: AppContext) -> None:
        super().__init__()
        self.setWindowTitle("GAVEL")

        self._registry = registry
        self._ctx = ctx

        self._stack = QStackedWidget()
        self._page_widgets: dict[str, QWidget] = {}
        self._page_specs: dict[str, PageSpec] = {}

        pages = self._registry.list_pages()
        self._page_specs = {p.page_id: p for p in pages}

        self._drawer = NavigationDrawer(self._ctx.theme, pages, self.navigate_to)

        shell = QWidget()
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._drawer)
        root.addWidget(self._stack, 1)

        self.setCentralWidget(shell)

        # Under every page. The course chip only shows on pages that use the active course.
        self._course_chip = ActiveCourseChip(self._ctx.theme, self._ctx.active_course)
        self._workspace_label = QLabel(str(self._ctx.active_course.workspace.root))
        self._workspace_label.setProperty("role", "text_muted")
        self._workspace_label.setToolTip("Workspace folder (DEFAULT_OUTPUT_DIR)")
        status_bar = QStatusBar()
        status_bar.setSizeGripEnabled(False)
        status_bar.addWidget(self._course_chip)
        status_bar.addPermanentWidget(self._workspace_label)
        self.setStatusBar(status_bar)

        if pages:
            self.navigate_to(pages[0].page_id)

    @property
    def course_chip(self) -> ActiveCourseChip:
        return self._course_chip

    @property
    def workspace_label(self) -> QLabel:
        return self._workspace_label

    def navigate_to(self, page_id: str) -> None:
        widget = self._ensure_page(page_id)
        self._stack.setCurrentWidget(widget)
        self._drawer.set_current(page_id)

        uses_course = self._page_specs[page_id].uses_active_course
        self._course_chip.setVisible(uses_course)
        if uses_course:
            # The picked folder may have been deleted or renamed since.
            self._ctx.active_course.revalidate()

    def _ensure_page(self, page_id: str) -> QWidget:
        if page_id in self._page_widgets:
            return self._page_widgets[page_id]

        spec = self._page_specs[page_id]
        widget = spec.factory(self._ctx)
        if spec.uses_active_course:
            widget = ActiveCourseGate(
                self._ctx.theme,
                self._ctx.active_course,
                spec.title,
                widget,
                self._course_chip.popup,
            )

        self._page_widgets[page_id] = widget
        self._stack.addWidget(widget)
        return widget
