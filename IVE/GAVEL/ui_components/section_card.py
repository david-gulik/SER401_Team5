from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing


class SectionCard(QFrame):
    def __init__(self, theme: ThemeContext, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "surface")

        root = QVBoxLayout(self)
        root.setContentsMargins(
            theme.tokens.sp(16),
            theme.tokens.sp(16),
            theme.tokens.sp(16),
            theme.tokens.sp(16),
        )
        set_spacing(root, theme, 12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        set_spacing(header, theme, 8)

        self._title = QLabel(title)
        self._title.setProperty("role", "h2")

        self._actions = QWidget(self)
        self._actions_layout = QHBoxLayout(self._actions)
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(self._actions_layout, theme, 8)
        self._actions_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._actions)

        self._body = QWidget(self)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(self._body_layout, theme, 8)
        self._body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        root.addLayout(header)
        root.addWidget(self._body)

    def add_action(self, widget: QWidget) -> None:
        self._actions_layout.addWidget(widget)

    def add_row(self, widget: QWidget) -> None:
        self._body_layout.addWidget(widget)

    def add_stretch(self) -> None:
        self._body_layout.addStretch(1)
