from __future__ import annotations

from typing import List, Tuple

from PyQt6.QtWidgets import QWidget


class BasePage(QWidget):
    """
    Base contract for a Page.

    A Page defines:
    - page_id, title
    - a list of tabs (tab_title, tab_widget)
    """

    page_id: str = "base"
    title: str = "Base"

    def build_tabs(self) -> List[Tuple[str, QWidget]]:
        raise NotImplementedError
