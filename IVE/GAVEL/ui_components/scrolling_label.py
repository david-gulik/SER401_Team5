from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QWidget


class ScrollingLabel(QScrollArea):
    """Word-wrapped, selectable text that grows with its content up to ``max_height``.

    Past that height the text scrolls instead of pushing the rest of the
    layout around, so a long status or error list stays a fixed size.
    """

    def __init__(self, max_height: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._max_height = max_height

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.setWidget(self._label)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt override)
        self._label.setText(text)
        self.updateGeometry()

    def text(self) -> str:
        return self._label.text()

    @property
    def label(self) -> QLabel:
        return self._label

    @property
    def max_height(self) -> int:
        return self._max_height

    def content_height(self) -> int:
        """Height the whole text needs at the current width."""
        # The widget's own width is current before the viewport is laid out; before
        # its first layout that width is a placeholder, so the minimum width wins.
        width = max(self.width(), self.minimumWidth()) - 2 * self.frameWidth()
        width = max(width, 1)
        return self._label.heightForWidth(width)

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        height = min(self.content_height(), self._max_height) + 2 * self.frameWidth()
        return QSize(super().sizeHint().width(), height)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        return QSize(super().minimumSizeHint().width(), self.sizeHint().height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        # Wrapping depends on width, so a new width can need a new height.
        if event.size().width() != event.oldSize().width():
            self.updateGeometry()
