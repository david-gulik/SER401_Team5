from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing


class AgreementBar(QWidget):
    """A thin bar split into the runs that agreed, differed, and gave no result.

    Proportional, so ten runs and a hundred read the same.
    """

    def __init__(
        self, theme: ThemeContext, agreed: int, changed: int, broke: int, parent=None
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self.agreed = max(0, agreed)
        self.changed = max(0, changed)
        self.broke = max(0, broke)
        self.setFixedSize(100, 8)
        self.setToolTip(f"{self.agreed} agreed · {self.changed} different · {self.broke} no result")

    @property
    def total(self) -> int:
        return self.agreed + self.changed + self.broke

    def paintEvent(self, event: QPaintEvent | None) -> None:
        colors = self._theme.tokens.color
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors["input_bg"]))
        painter.drawRoundedRect(QRectF(self.rect()), 2, 2)
        if self.total == 0:
            painter.end()
            return
        width = self.width()
        x = 0.0
        for count, token in (
            (self.agreed, "status_nominal"),
            (self.changed, "status_caution"),
            (self.broke, "status_critical"),
        ):
            if count == 0:
                continue
            span = width * count / self.total
            painter.setBrush(QColor(colors[token]))
            painter.drawRect(QRectF(x, 0, span, self.height()))
            x += span
        painter.end()


class AgreementCell(QWidget):
    """The bar beside its count, for a tree cell."""

    def __init__(
        self,
        theme: ThemeContext,
        agreed: int,
        changed: int,
        broke: int,
        text: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.bar = AgreementBar(theme, agreed, changed, broke, self)
        self.label = QLabel(text, self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        set_spacing(layout, theme, 8)
        layout.addWidget(self.bar)
        layout.addWidget(self.label, 1)

    @property
    def text(self) -> str:
        return self.label.text()
