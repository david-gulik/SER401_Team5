from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from GAVEL.core.status import Status, get_status_style
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing


class StatusPill(QWidget):
    """
    Small inline status indicator: colored dot + label.
    Styling:
    - container uses role="status_pill"
    - dot uses role="status_dot" with an inline color property
    """

    def __init__(self, theme: ThemeContext, status: Status = Status.UNKNOWN, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme

        self.setProperty("role", "status_pill")

        self._dot = QLabel("●", self)
        self._dot.setProperty("role", "status_dot")

        self._text = QLabel("", self)
        self._text.setProperty("role", "status_text")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        set_spacing(root, theme, 8)
        root.setAlignment(Qt.AlignmentFlag.AlignLeft)

        root.addWidget(self._dot)
        root.addWidget(self._text)

        self.set_status(status)

    def set_status(self, status: Status) -> None:
        style = get_status_style(self._theme, status)
        self._text.setText(style.label)

        # Dynamic property to enable QSS to color the dot
        self._dot.setStyleSheet(f"color: {style.color};")
