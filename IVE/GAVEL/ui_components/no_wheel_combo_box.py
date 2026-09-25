"""Combo box that leaves the mouse wheel to the enclosing scroll area."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QComboBox, QWidget


class NoWheelComboBox(QComboBox):
    """A ``QComboBox`` whose selection is never changed by the scroll wheel.

    The focus policy is lowered from the default ``WheelFocus`` to
    ``StrongFocus`` so the wheel does not move keyboard focus onto the combo
    either.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        if event is not None:
            event.ignore()
