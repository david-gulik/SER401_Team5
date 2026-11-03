from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import QWidget

from GAVEL.app_context import AppContext

# Sidebar sections, top to bottom; each name is also the heading drawn above its pages.
GROUP_ORDER: tuple[str, ...] = ("General", "Preparation", "Verification", "Analysis")


@dataclass(frozen=True)
class PageSpec:
    page_id: str
    title: str
    icon_text: str
    factory: Callable[[AppContext], QWidget]
    order: int = 100
    group: str = "General"
    icon_path: Path | None = None
    # The page works on the course picked in the status bar (see ActiveCourse): the
    # shell shows the course chip on it, and a "choose a course" card until one is picked.
    uses_active_course: bool = False


class PageRegistry:
    _instance: PageRegistry | None = None

    def __init__(self) -> None:
        self._pages: dict[str, PageSpec] = {}

    @classmethod
    def get(cls) -> PageRegistry:
        if cls._instance is None:
            cls._instance = PageRegistry()
        return cls._instance

    def register(self, spec: PageSpec) -> None:
        if spec.page_id in self._pages:
            raise ValueError(f"Duplicate page_id registered: {spec.page_id}")
        self._pages[spec.page_id] = spec

    def list_pages(self) -> list[PageSpec]:
        """Pages in sidebar order: by group (see GROUP_ORDER), then by order within a group."""
        return sorted(
            self._pages.values(),
            key=lambda p: (_group_rank(p.group), p.group, p.order),
        )

    def get_page(self, page_id: str) -> PageSpec:
        return self._pages[page_id]


def _group_rank(group: str) -> int:
    try:
        return GROUP_ORDER.index(group)
    except ValueError:
        return len(GROUP_ORDER)
