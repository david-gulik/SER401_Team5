from __future__ import annotations

from GAVEL.ui_components.chart_canvas import ChartCanvas


def test_starts_with_placeholder_visible(qapp, theme):
    canvas = ChartCanvas(theme, placeholder_text="Nothing yet")
    assert not canvas.is_showing_chart()


def test_draw_switches_to_the_chart(qapp, theme):
    canvas = ChartCanvas(theme)
    canvas.figure.add_subplot().plot([1, 2, 3], [1, 2, 3])
    canvas.draw()
    assert canvas.is_showing_chart()


def test_clear_returns_to_the_placeholder(qapp, theme):
    canvas = ChartCanvas(theme)
    canvas.figure.add_subplot().plot([1, 2, 3], [1, 2, 3])
    canvas.draw()
    canvas.clear()
    assert not canvas.is_showing_chart()
