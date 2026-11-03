from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtCore import QSettings

import GAVEL.pages.autograders.page  # noqa: F401
from GAVEL.app.workspace.layout import Workspace
from GAVEL.core.active_course import ActiveCourse
from GAVEL.core.page_registry import PageRegistry
from GAVEL.pages.inspect_grades.page import InspectGradesPage
from GAVEL.pages.inspect_grades.tabs import InspectGradesTab

TEST_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "workspace"


def _ctx(theme, tmp_path: Path, workspace_root: Path) -> SimpleNamespace:
    settings = QSettings(str(tmp_path / "gavel.ini"), QSettings.Format.IniFormat)
    return SimpleNamespace(
        theme=theme,
        services=SimpleNamespace(dataset_readers=None),
        active_course=ActiveCourse(Workspace(workspace_root), settings),
    )


def test_inspect_grades_page_is_registered():
    spec = PageRegistry.get().get_page("inspect_grades")

    assert spec.title == "Inspect Grades"
    assert spec.group == "Verification"
    assert spec.uses_active_course


def test_inspect_grades_sits_directly_below_autograders():
    page_ids = [spec.page_id for spec in PageRegistry.get().list_pages()]

    assert page_ids[page_ids.index("autograders") + 1] == "inspect_grades"


def test_factory_builds_page_with_one_inspect_grades_tab(qapp, theme, tmp_path):
    spec = PageRegistry.get().get_page("inspect_grades")

    page = spec.factory(_ctx(theme, tmp_path, tmp_path))

    assert isinstance(page, InspectGradesPage)
    assert len(page.findChildren(InspectGradesTab)) == 1

    page.deleteLater()


def test_page_follows_the_active_course(qapp, theme, tmp_path):
    ctx = _ctx(theme, tmp_path, TEST_WORKSPACE)
    page = PageRegistry.get().get_page("inspect_grades").factory(ctx)
    [tab] = page.findChildren(InspectGradesTab)
    assert tab.assignment_combo.count() == 1

    [course] = ctx.active_course.workspace.list_courses()
    ctx.active_course.select(course)

    assert tab.assignment_combo.count() == 3

    page.deleteLater()


def test_page_starts_on_the_course_that_is_already_active(qapp, theme, tmp_path):
    ctx = _ctx(theme, tmp_path, TEST_WORKSPACE)
    [course] = ctx.active_course.workspace.list_courses()
    ctx.active_course.select(course)

    page = PageRegistry.get().get_page("inspect_grades").factory(ctx)

    [tab] = page.findChildren(InspectGradesTab)
    assert tab.assignment_combo.count() == 3

    page.deleteLater()
