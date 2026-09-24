"""Reusable Matplotlib/Seaborn chart embedding for the GAVEL GUI.

Wraps ``FigureCanvasQTAgg`` behind a small widget so analytics pages can add
and swap charts without each one wiring up the embedding boilerplate itself.
Seaborn draws onto the same ``figure``/``axes`` objects Matplotlib exposes,
so nothing seaborn-specific is needed here.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from GAVEL.theme.context import ThemeContext


class ChartCanvas(QWidget):
    """Embeds a single Matplotlib figure, with an empty-state placeholder.

    Callers plot onto ``figure`` directly, then call ``draw()`` to render it
    and switch off the placeholder. ``clear()`` discards the figure contents
    and brings the placeholder back, e.g. before redrawing with new data.
    """

    def __init__(
        self,
        theme: ThemeContext,
        *,
        placeholder_text: str = "No chart data yet.",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme

        self.figure = Figure()
        self._canvas = FigureCanvasQTAgg(self.figure)

        self._placeholder = QLabel(placeholder_text, self)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setProperty("role", "text_muted")
        self._placeholder.setWordWrap(True)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._canvas)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

    def draw(self) -> None:
        """Render the figure's current contents and show it in place of the placeholder."""
        self._canvas.draw()
        self._stack.setCurrentWidget(self._canvas)

    def clear(self) -> None:
        """Discard the figure's contents and show the placeholder again."""
        self.figure.clear()
        self._stack.setCurrentWidget(self._placeholder)

    def is_showing_chart(self) -> bool:
        """True once ``draw()`` has run more recently than ``clear()``."""
        return self._stack.currentWidget() is self._canvas
