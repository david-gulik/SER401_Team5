"""Reusable Matplotlib/Seaborn chart embedding for the GAVEL GUI.

Wraps ``FigureCanvasQTAgg`` behind a small widget so analytics pages can add
and swap charts without each one wiring up the embedding boilerplate itself.
Seaborn draws onto the same ``figure``/``axes`` objects Matplotlib exposes,
so nothing seaborn-specific is needed here.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QLabel, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from GAVEL.theme.context import ThemeContext

_MINIMUM_HEIGHT = 320


class ChartCanvas(QWidget):
    """Embeds a Matplotlib figure with an empty-state placeholder.

    Callers plot onto ``figure`` directly, then call ``draw()`` to render it
    and switch off the placeholder. ``clear()`` discards the figure contents
    and brings the placeholder back, e.g. before redrawing with new data.
    A NavigationToolbar2QT above the chart gives pan, zoom, home, and export
    controls. It is hidden while the placeholder is showing.
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

        self.figure = Figure(layout="constrained")
        self._canvas = FigureCanvasQTAgg(self.figure)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        self._toolbar.setVisible(False)
        self._style_toolbar_icons(theme)

        self._placeholder = QLabel(placeholder_text, self)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setProperty("role", "text_muted")
        self._placeholder.setWordWrap(True)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._canvas)
        self._stack.setMinimumHeight(_MINIMUM_HEIGHT)
        self._stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._toolbar)
        root.addWidget(self._stack)

    def draw(self) -> None:
        """Render the figure's current contents and show it in place of the placeholder.

        The figure uses constrained layout (set at construction), so axis
        labels stay inside its bounds even as this widget gets resized.
        Resets the toolbar's pan/zoom history, then records this view as
        home.
        """
        self._canvas.draw()
        self._toolbar.update()
        self._toolbar.push_current()
        self._stack.setCurrentWidget(self._canvas)
        self._toolbar.setVisible(True)

    def clear(self) -> None:
        """Discard the figure's contents and show the placeholder again."""
        self.figure.clear()
        self._stack.setCurrentWidget(self._placeholder)
        self._toolbar.setVisible(False)

    def is_showing_chart(self) -> bool:
        """True once ``draw()`` has run more recently than ``clear()``."""
        return self._stack.currentWidget() is self._canvas

    def _style_toolbar_icons(self, theme: ThemeContext) -> None:
        """Matches the toolbar's palette to the app's theme."""
        palette = self._toolbar.palette()
        palette.setColor(QPalette.ColorRole.Button, QColor(theme.tokens.color["surface"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.tokens.color["text"]))
        self._toolbar.setPalette(palette)
