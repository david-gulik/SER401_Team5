from __future__ import annotations

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT

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


def test_toolbar_is_hidden_while_the_placeholder_is_showing(qapp, theme):
    canvas = ChartCanvas(theme)
    canvas.show()

    [toolbar] = canvas.findChildren(NavigationToolbar2QT)
    assert not toolbar.isVisible()


def test_toolbar_appears_once_a_chart_is_drawn(qapp, theme):
    canvas = ChartCanvas(theme)
    canvas.show()
    canvas.figure.add_subplot().plot([1, 2, 3], [1, 2, 3])

    canvas.draw()

    [toolbar] = canvas.findChildren(NavigationToolbar2QT)
    assert toolbar.isVisible()


def test_toolbar_hides_again_after_clear(qapp, theme):
    canvas = ChartCanvas(theme)
    canvas.show()
    canvas.figure.add_subplot().plot([1, 2, 3], [1, 2, 3])
    canvas.draw()

    canvas.clear()

    [toolbar] = canvas.findChildren(NavigationToolbar2QT)
    assert not toolbar.isVisible()


def test_home_restores_the_view_after_a_zoom(qapp, theme):
    canvas = ChartCanvas(theme)
    axes = canvas.figure.add_subplot()
    axes.plot([0, 1], [0, 1])
    canvas.draw()
    original_xlim = axes.get_xlim()
    axes.set_xlim(0.2, 0.8)

    canvas._toolbar.home()

    assert axes.get_xlim() == original_xlim


def test_redrawing_resets_the_pan_zoom_history(qapp, theme):
    canvas = ChartCanvas(theme)
    canvas.figure.add_subplot().plot([0, 1], [0, 1])
    canvas.draw()

    canvas.clear()
    canvas.figure.add_subplot().plot([0, 1], [1, 0])
    canvas.draw()

    assert len(canvas._toolbar._nav_stack) == 1


def test_toolbar_icons_are_recolored_for_the_dark_theme(qapp, theme):
    canvas = ChartCanvas(theme)

    [toolbar] = canvas.findChildren(NavigationToolbar2QT)
    assert toolbar.palette().color(toolbar.backgroundRole()).value() < 128
