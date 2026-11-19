from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtCore import QSettings
from PyQt6.QtSvg import QSvgRenderer

import GAVEL.pages.autograders.page  # noqa: F401
import GAVEL.pages.inspect_grades.page  # noqa: F401
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.core.active_course import ActiveCourse
from GAVEL.core.page_registry import PageRegistry
from GAVEL.pages.stability_check.page import StabilityCheckPage
from GAVEL.pages.stability_check.tabs import StabilityCheckTab
from tests.fakes.autograder_runner import FakeAutograderRunner


def _ctx(theme, tmp_path: Path, workspace) -> SimpleNamespace:
    settings = QSettings(str(tmp_path / "gavel.ini"), QSettings.Format.IniFormat)
    return SimpleNamespace(
        theme=theme,
        services=SimpleNamespace(
            dataset_readers=build_dataset_readers(), autograder_runner=FakeAutograderRunner()
        ),
        active_course=ActiveCourse(workspace, settings),
    )


def test_the_page_is_registered_in_verification():
    spec = PageRegistry.get().get_page("stability_check")

    assert spec.title == "Stability Check"
    assert spec.group == "Verification"
    assert spec.uses_active_course


def test_the_page_sits_between_autograders_and_inspect_grades():
    page_ids = [spec.page_id for spec in PageRegistry.get().list_pages()]

    start = page_ids.index("autograders")
    assert page_ids[start : start + 3] == ["autograders", "stability_check", "inspect_grades"]


def test_the_icon_is_a_valid_svg(qapp):
    spec = PageRegistry.get().get_page("stability_check")

    assert spec.icon_path is not None
    assert QSvgRenderer(str(spec.icon_path)).isValid()


def test_the_factory_builds_the_page_around_one_tab(qapp, theme, tmp_path, workspace):
    page = PageRegistry.get().get_page("stability_check").factory(_ctx(theme, tmp_path, workspace))

    assert isinstance(page, StabilityCheckPage)
    assert len(page.findChildren(StabilityCheckTab)) == 1

    page.deleteLater()


def test_the_page_follows_the_active_course(qapp, theme, tmp_path, workspace, course):
    ctx = _ctx(theme, tmp_path, workspace)
    page = PageRegistry.get().get_page("stability_check").factory(ctx)
    [tab] = page.findChildren(StabilityCheckTab)
    assert tab.assignment_combo.count() == 1

    ctx.active_course.select(course)

    assert tab.assignment_combo.count() == 3

    page.deleteLater()


def test_the_page_starts_on_the_course_already_active(qapp, theme, tmp_path, workspace, course):
    ctx = _ctx(theme, tmp_path, workspace)
    ctx.active_course.select(course)

    page = PageRegistry.get().get_page("stability_check").factory(ctx)

    [tab] = page.findChildren(StabilityCheckTab)
    assert tab.assignment_combo.count() == 3

    page.deleteLater()
