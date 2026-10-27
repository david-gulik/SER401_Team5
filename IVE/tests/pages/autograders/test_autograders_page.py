from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtSvg import QSvgRenderer

import GAVEL.pages.download.page  # noqa: F401
from GAVEL.core.page_registry import PageRegistry
from GAVEL.pages.autograders.page import AutogradersPage
from GAVEL.pages.autograders.tabs import AutogradersDiagnosticsPage, RunAutogradersTab


def test_sanitize_page_is_registered():
    spec = PageRegistry.get().get_page("autograders")

    assert spec.title == "Autograders"
    assert spec.uses_active_course


def test_sanitize_icon_is_a_valid_svg(qapp):
    spec = PageRegistry.get().get_page("autograders")

    assert spec.icon_path is not None
    assert QSvgRenderer(str(spec.icon_path)).isValid()


def test_factory_builds_the_page_around_one_of_each_autograders_tab(qapp, theme):
    spec = PageRegistry.get().get_page("autograders")

    page = spec.factory(SimpleNamespace(theme=theme))

    assert isinstance(page, AutogradersPage)
    assert len(page.findChildren(RunAutogradersTab)) == 1
    assert len(page.findChildren(AutogradersDiagnosticsPage)) == 1
