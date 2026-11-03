from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from GAVEL.ui_components.scrolling_label import ScrollingLabel

MESSAGE_MAX_HEIGHT = 320
MESSAGE_WIDTH = 420
# The smallest the text area can be dragged to.
MESSAGE_MIN_HEIGHT = 60


class MessageDialog(QDialog):
    """An information or error popup whose text scrolls once it gets long.

    QMessageBox grows to fit its text, which for a batch download summary can
    be taller than the screen. This opens fitted to the text, up to
    MESSAGE_MAX_HEIGHT, and can then be resized; the text area grows with it.
    The text can still be selected and copied.
    """

    def __init__(
        self, parent: QWidget | None, title: str, text: str, critical: bool = False
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setSizeGripEnabled(True)

        pixmap = (
            QStyle.StandardPixmap.SP_MessageBoxCritical
            if critical
            else QStyle.StandardPixmap.SP_MessageBoxInformation
        )
        icon = QLabel()
        icon.setPixmap(self.style().standardIcon(pixmap).pixmap(32, 32))
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._message = ScrollingLabel(MESSAGE_MAX_HEIGHT)
        self._message.setMinimumSize(MESSAGE_WIDTH, MESSAGE_MIN_HEIGHT)
        self._message.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._message.setText(text)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(icon)
        body.addWidget(self._message, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)

        root = QVBoxLayout(self)
        root.addLayout(body, 1)
        root.addWidget(buttons)

    @property
    def message(self) -> ScrollingLabel:
        return self._message


def show_message(parent: QWidget | None, title: str, text: str, critical: bool = False) -> None:
    """Show a MessageDialog and wait for it to be closed."""
    MessageDialog(parent, title, text, critical).exec()
