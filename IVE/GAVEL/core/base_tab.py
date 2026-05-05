from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_margins, set_spacing


class ScrollableTab(QWidget):
    def __init__(self, theme: ThemeContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._theme = theme

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)

        self._content = QWidget()
        self._layout = QVBoxLayout(self._content)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        set_spacing(self._layout, theme, 12)
        set_margins(self._layout, theme, 16)

        self._scroll.setWidget(self._content)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._scroll)

    def add_section(self, section: QWidget) -> None:
        self._layout.addWidget(section)

    def add_stretch(self) -> None:
        self._layout.addStretch(1)
