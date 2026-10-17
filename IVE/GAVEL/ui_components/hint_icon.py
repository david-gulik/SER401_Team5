from __future__ import annotations

from PyQt6.QtWidgets import QLabel


def hint_icon(tooltip: str) -> QLabel:
    """A small circled "?" explaining a card's requirements on hover."""
    icon = QLabel("?")
    icon.setProperty("role", "hint_icon")
    icon.setFixedSize(16, 16)
    icon.setToolTip(tooltip)
    return icon
