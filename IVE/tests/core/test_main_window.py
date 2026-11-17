from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel

from GAVEL.app.workspace.layout import Workspace
from GAVEL.core.active_course import ActiveCourse
from GAVEL.core.course_selector import ActiveCourseGate
from GAVEL.core.main_window import MainWindow
from GAVEL.core.page_registry import PageRegistry, PageSpec

COURSE = "ser222_26f_11111"


def ctx(theme, tmp_path: Path) -> SimpleNamespace:
    settings = QSettings(str(tmp_path / "gavel.ini"), QSettings.Format.IniFormat)
    return SimpleNamespace(theme=theme, active_course=ActiveCourse(Workspace(tmp_path), settings))


def registry() -> PageRegistry:
    registry = PageRegistry()
    registry.register(
        PageSpec(
            page_id="plain",
            title="Plain",
            icon_text="",
            factory=lambda ctx: QLabel("plain"),
            order=10,
        )
    )
    registry.register(
        PageSpec(
            page_id="scoped",
            title="Scoped",
            icon_text="",
            factory=lambda ctx: QLabel("scoped"),
            order=20,
            uses_active_course=True,
        )
    )
    return registry


def test_the_course_chip_shows_only_on_pages_that_use_the_active_course(qapp, theme, tmp_path):
    window = MainWindow(registry(), ctx(theme, tmp_path))
    assert window.course_chip.isHidden()

    window.navigate_to("scoped")
    assert not window.course_chip.isHidden()

    window.navigate_to("plain")
    assert window.course_chip.isHidden()


def test_the_status_bar_names_the_workspace(qapp, theme, tmp_path):
    window = MainWindow(registry(), ctx(theme, tmp_path))

    assert window.workspace_label.text() == str(tmp_path)


def test_a_plain_page_is_shown_as_is(qapp, theme, tmp_path):
    window = MainWindow(registry(), ctx(theme, tmp_path))

    window.navigate_to("plain")

    current = window._stack.currentWidget()
    assert isinstance(current, QLabel)
    assert current.text() == "plain"


def test_a_scoped_page_waits_behind_the_choose_course_card(qapp, theme, tmp_path):
    (tmp_path / "courses" / COURSE).mkdir(parents=True)
    context = ctx(theme, tmp_path)
    window = MainWindow(registry(), context)

    window.navigate_to("scoped")

    gate = window._stack.currentWidget()
    assert isinstance(gate, ActiveCourseGate)
    assert gate.currentWidget() is gate.card

    [course] = context.active_course.workspace.list_courses()
    context.active_course.select(course)

    assert gate.currentWidget() is gate.page
    assert isinstance(gate.page, QLabel)
    assert gate.page.text() == "scoped"


def test_opening_a_scoped_page_drops_a_course_whose_folder_is_gone(qapp, theme, tmp_path):
    folder = tmp_path / "courses" / COURSE
    folder.mkdir(parents=True)
    context = ctx(theme, tmp_path)
    [course] = context.active_course.workspace.list_courses()
    context.active_course.select(course)
    window = MainWindow(registry(), context)
    shutil.rmtree(folder)

    window.navigate_to("scoped")

    assert context.active_course.course is None
