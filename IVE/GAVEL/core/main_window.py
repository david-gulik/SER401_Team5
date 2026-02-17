from __future__ import annotations

from typing import Dict

from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from GAVEL.app_context import AppContext
from GAVEL.core.navigation_drawer import NavigationDrawer
from GAVEL.core.page_registry import PageRegistry, PageSpec


class MainWindow(QMainWindow):
    def __init__(self, registry: PageRegistry, ctx: AppContext) -> None:
        super().__init__()
        self.setWindowTitle("Modular PyQt App")

        self._registry = registry
        self._ctx = ctx

        self._stack = QStackedWidget()
        self._page_widgets: Dict[str, QWidget] = {}
        self._page_specs: Dict[str, PageSpec] = {}

        pages = self._registry.list_pages()
        self._page_specs = {p.page_id: p for p in pages}

        self._drawer = NavigationDrawer(self._ctx.theme, pages, self.navigate_to)

        shell = QWidget()
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._drawer)
        root.addWidget(self._stack, 1)

        self.setCentralWidget(shell)

        if pages:
            self.navigate_to(pages[0].page_id)

    def navigate_to(self, page_id: str) -> None:
        widget = self._ensure_page(page_id)
        self._stack.setCurrentWidget(widget)
        self._drawer.set_current(page_id)

    def _ensure_page(self, page_id: str) -> QWidget:
        if page_id in self._page_widgets:
            return self._page_widgets[page_id]

        spec = self._page_specs[page_id]
        widget = spec.factory(self._ctx)

        self._page_widgets[page_id] = widget
        self._stack.addWidget(widget)
        return widget
