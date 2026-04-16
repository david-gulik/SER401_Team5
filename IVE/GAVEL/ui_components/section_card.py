from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing


class SectionCard(QFrame):
    def __init__(
        self, theme: ThemeContext, title: str, parent: QWidget | None = None, role: str = "panel_bg"
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", role)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Title region
        self._header = QFrame(self)
        self._header.setProperty("role", "card_header")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(
            theme.tokens.sp(16),
            theme.tokens.sp(12),
            theme.tokens.sp(16),
            theme.tokens.sp(12),
        )
        set_spacing(header_layout, theme, 8)

        self._title = QLabel(title)
        self._title.setProperty("role", "h2")

        self._actions = QWidget(self._header)
        self._actions_layout = QHBoxLayout(self._actions)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(self._actions_layout, theme, 8)
        self._actions_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        header_layout.addWidget(self._title)
        header_layout.addStretch(1)
        header_layout.addWidget(self._actions)

        # Body
        self._body = QWidget(self)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(
            theme.tokens.sp(16),
            theme.tokens.sp(16),
            theme.tokens.sp(16),
            theme.tokens.sp(16),
        )
        set_spacing(self._body_layout, theme, 8)
        self._body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        root.addWidget(self._header)
        root.addWidget(self._body)

    def add_action(self, widget: QWidget) -> None:
        self._actions_layout.addWidget(widget)

    def add_row(self, widget: QWidget) -> None:
        self._body_layout.addWidget(widget)

    def add_stretch(self) -> None:
        self._body_layout.addStretch(1)
