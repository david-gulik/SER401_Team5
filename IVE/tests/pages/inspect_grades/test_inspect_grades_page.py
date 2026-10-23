from __future__ import annotations

from types import SimpleNamespace

import GAVEL.pages.analytics.page  # noqa: F401
from GAVEL.core.page_registry import PageRegistry
from GAVEL.pages.inspect_grades.page import InspectGradesPage
from GAVEL.pages.inspect_grades.tabs import InspectGradesTab
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel


def test_inspect_grades_page_is_registered():
    spec = PageRegistry.get().get_page("inspect_grades")

    assert spec.title == "Inspect Grades"
    assert spec.group == "Analytics"


def test_inspect_grades_sits_directly_below_analytics():
    page_ids = [spec.page_id for spec in PageRegistry.get().list_pages()]

    assert page_ids[page_ids.index("analytics") + 1] == "inspect_grades"


def test_factory_builds_page_with_one_inspect_grades_tab(qapp, theme, tmp_path, monkeypatch):
    monkeypatch.setenv("DEFAULT_OUTPUT_DIR", str(tmp_path))

    spec = PageRegistry.get().get_page("inspect_grades")

    ctx = SimpleNamespace(
        theme=theme,
        services=SimpleNamespace(dataset_readers=None),
    )

    page = spec.factory(ctx)

    assert isinstance(page, InspectGradesPage)
    assert len(page.findChildren(InspectGradesTab)) == 1

    page.deleteLater()


def test_inspect_grades_tab_displays_selectors(qapp, theme, tmp_path):
    vm = InspectGradesViewModel(
        workspace_root=tmp_path,
        dataset_readers=None,
    )

    tab = InspectGradesTab(theme, vm)

    assert tab.course_combo.count() == 1
    assert tab.course_combo.itemText(0) == "Select a course"

    assert tab.assignment_combo.count() == 1
    assert tab.assignment_combo.itemText(0) == "Select an assignment"

    assert not tab.assignment_combo.isEnabled()
    assert tab.status_label.text() == "Select a course to view assignments."

    tab.deleteLater()
