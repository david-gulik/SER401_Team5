from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtSvg import QSvgRenderer

import GAVEL.pages.download.page  # noqa: F401
from GAVEL.core.page_registry import PageRegistry
from GAVEL.pages.sanitize.page import SanitizePage
from GAVEL.pages.sanitize.tabs import SanitizeTab
from GAVEL.pages.sanitize.viewmodel import SanitizeUiState, SanitizeViewModel


def test_sanitize_page_is_registered():
    spec = PageRegistry.get().get_page("sanitize")

    assert spec.title == "Sanitize"


def test_sanitize_page_sits_directly_below_download():
    page_ids = [spec.page_id for spec in PageRegistry.get().list_pages()]

    assert page_ids[page_ids.index("download") + 1] == "sanitize"


def test_sanitize_icon_is_a_valid_svg(qapp):
    spec = PageRegistry.get().get_page("sanitize")

    assert spec.icon_path is not None
    assert QSvgRenderer(str(spec.icon_path)).isValid()


def test_factory_builds_the_page_around_one_sanitize_tab(qapp, theme):
    spec = PageRegistry.get().get_page("sanitize")

    page = spec.factory(SimpleNamespace(theme=theme))

    assert isinstance(page, SanitizePage)
    assert len(page.findChildren(SanitizeTab)) == 1


def test_tab_paints_the_initial_state_and_every_change(qapp, theme, monkeypatch):
    painted: list[SanitizeUiState] = []
    monkeypatch.setattr(SanitizeTab, "render", lambda self, state: painted.append(state))
    vm = SanitizeViewModel()

    tab = SanitizeTab(theme, vm)
    vm.state_changed.emit(SanitizeUiState())

    assert painted == [SanitizeUiState(), SanitizeUiState()]
    tab.deleteLater()
