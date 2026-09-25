from __future__ import annotations

from GAVEL.pages.analytics.tabs import OverviewTab
from GAVEL.ui_components.chart_canvas import ChartCanvas


def test_overview_tab_starts_with_an_empty_placeholder_chart(qapp, theme):
    tab = OverviewTab(theme)

    canvases = tab.findChildren(ChartCanvas)

    assert len(canvases) == 1
    assert not canvases[0].is_showing_chart()
