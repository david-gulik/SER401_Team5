from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtWidgets import QLabel

import GAVEL.pages.analytics.page  # noqa: F401
from GAVEL.core.page_registry import PageRegistry
from GAVEL.pages.inspect_grades.page import InspectGradesPage
from GAVEL.pages.inspect_grades.tabs import InspectGradesTab


def test_inspect_grades_page_is_registered():
    spec = PageRegistry.get().get_page("inspect_grades")

    assert spec.title == "Inspect Grades"
    assert spec.group == "Analytics"


def test_inspect_grades_sits_directly_below_analytics():
    page_ids = [spec.page_id for spec in PageRegistry.get().list_pages()]

    assert page_ids[page_ids.index("analytics") + 1] == "inspect_grades"


def test_factory_builds_page_with_one_inspect_grades_tab(qapp, theme):
    spec = PageRegistry.get().get_page("inspect_grades")

    page = spec.factory(SimpleNamespace(theme=theme))

    assert isinstance(page, InspectGradesPage)
    assert len(page.findChildren(InspectGradesTab)) == 1

    page.deleteLater()


def test_inspect_grades_tab_displays_placeholder(qapp, theme):
    tab = InspectGradesTab(theme)

    labels = tab.findChildren(QLabel)

    assert any(label.text() == "TODO: Grade inspection features" for label in labels)

    tab.deleteLater()
