from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from PyQt6.QtWidgets import QWidget

from GAVEL.app_context import AppContext


@dataclass(frozen=True)
class PageSpec:
    page_id: str
    title: str
    icon_text: str
    factory: Callable[[AppContext], QWidget]
    order: int = 100
    group: str = "General"


class PageRegistry:
    _instance: Optional["PageRegistry"] = None

    def __init__(self) -> None:
        self._pages: Dict[str, PageSpec] = {}

    @classmethod
    def get(cls) -> "PageRegistry":
        if cls._instance is None:
            cls._instance = PageRegistry()
        return cls._instance

    def register(self, spec: PageSpec) -> None:
        if spec.page_id in self._pages:
            raise ValueError(f"Duplicate page_id registered: {spec.page_id}")
        self._pages[spec.page_id] = spec

    def list_pages(self) -> List[PageSpec]:
        return sorted(self._pages.values(), key=lambda p: (p.group, p.order))

    def get_page(self, page_id: str) -> PageSpec:
        return self._pages[page_id]
