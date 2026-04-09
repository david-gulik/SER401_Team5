from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_margins, set_spacing


class SubPanel(QFrame):
    """Inner bordered panel with a title, used inside a SectionCard body."""

    def __init__(
        self, theme: ThemeContext, title: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "surface")

        root = QVBoxLayout(self)
        set_margins(root, theme, 12)
        set_spacing(root, theme, 8)

        self._title = QLabel(title)
        self._title.setProperty("role", "h3")
        root.addWidget(self._title)

        self._body = QWidget(self)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(self._body_layout, theme, 8)
        root.addWidget(self._body)

    def add_widget(self, widget: QWidget) -> None:
        self._body_layout.addWidget(widget)
