"""DownloadTab wiring for the myASU Term InputModeToggle.

Drives the real tab and view model against in-memory clients, offscreen.
Download actions are never triggered here: they end in a modal dialog.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QThreadPool

from GAVEL.app.dtos.roster import TermInfo
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import DownloadViewModel
from GAVEL.services.logger import AppLogger
from GAVEL.ui_components.input_mode_toggle import InputMode
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

TERMS = [
    TermInfo("2261", "Spring 2026"),
    TermInfo("2267", "Fall 2026", default=True),
    TermInfo("2271", "Spring 2027"),
]
DEFAULT = "2267"
TYPED = "2251"


def pump(qapp) -> None:
    for _ in range(5):
        qapp.processEvents()


def wait_for_workers(qapp) -> None:
    assert QThreadPool.globalInstance().waitForDone(5000)
    pump(qapp)


def build(qapp, theme, tmp_path: Path, configured: bool = True) -> SimpleNamespace:
    roster = FakeRosterClient(terms=TERMS, configured=configured)
    vm = DownloadViewModel(
        roster_client=roster,
        canvas_client=FakeCanvasClient(),
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=configured,
    )
    tab = DownloadTab(theme, vm)
    pump(qapp)
    return SimpleNamespace(tab=tab, vm=vm, roster=roster, term=tab.term_input)


@pytest.fixture
def env(qapp, theme, tmp_path: Path, monkeypatch) -> SimpleNamespace:
    monkeypatch.delenv("CANVAS_TOKEN", raising=False)  # keep Canvas out of these tests
    return build(qapp, theme, tmp_path)


def selected_term(env) -> str:
    return env.vm.get_state().selected_term


def load_terms(env, qapp) -> None:
    env.term.picker().load_button.click()
    wait_for_workers(qapp)


def test_only_one_term_input_is_visible_at_a_time(env):
    term = env.term
    assert term.mode() is InputMode.PICKER
    assert term.picker().isVisibleTo(term)
    assert not term.manual_field().isVisibleTo(term)
    term.set_mode(InputMode.MANUAL)
    assert not term.picker().isVisibleTo(term)
    assert term.manual_field().isVisibleTo(term)


def test_load_terms_fills_the_list_and_preselects_the_default(qapp, env):
    assert selected_term(env) == ""
    load_terms(env, qapp)
    combo = env.term.picker().combo
    assert combo.count() == 3
    assert combo.currentData() == DEFAULT
    assert selected_term(env) == DEFAULT
    assert env.term.readout_text() == "2267  Fall 2026"


def test_picking_another_term_updates_the_view_model(qapp, env):
    load_terms(env, qapp)
    env.term.picker().combo.setCurrentIndex(2)
    assert selected_term(env) == "2271"


def test_manual_term_code_is_used_when_valid(env):
    env.term.set_mode(InputMode.MANUAL)
    env.term.manual_field().setText(TYPED)
    assert env.term.is_valid()
    assert selected_term(env) == TYPED


def test_malformed_term_code_gives_inline_feedback_and_blocks_roster(env):
    env.term.set_mode(InputMode.MANUAL)
    env.term.manual_field().setText("22F7")
    assert not env.term.is_valid()
    assert selected_term(env) == ""
    env.tab.section_input.set_mode(InputMode.MANUAL)
    env.tab.section_input.manual_field().setText("12345")
    assert not env.tab._download_roster_btn.isEnabled()


def test_switching_modes_swaps_the_resolved_term(qapp, env):
    load_terms(env, qapp)
    env.term.set_mode(InputMode.MANUAL)
    env.term.manual_field().setText(TYPED)
    assert selected_term(env) == TYPED
    env.term.set_mode(InputMode.PICKER)
    assert selected_term(env) == DEFAULT


def test_valid_term_and_class_number_enable_roster_download(env):
    env.term.set_mode(InputMode.MANUAL)
    env.term.manual_field().setText(TYPED)
    env.tab.section_input.set_mode(InputMode.MANUAL)
    env.tab.section_input.manual_field().setText("12345")
    assert env.tab._download_roster_btn.isEnabled()


def test_load_terms_does_not_scroll_the_page_away(qapp, env):
    tab = env.tab
    tab.resize(900, 700)
    tab.show()
    tab.activateWindow()
    pump(qapp)
    load_button = env.term.picker().load_button
    load_button.setFocus()
    pump(qapp)
    assert qapp.focusWidget() is load_button
    scrollbar = tab._scroll.verticalScrollBar()
    assert scrollbar.value() == 0

    load_button.click()
    wait_for_workers(qapp)

    assert scrollbar.value() == 0
    assert qapp.focusWidget() is load_button


def test_unconfigured_roster_forces_manual_term_entry(qapp, theme, tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CANVAS_TOKEN", raising=False)
    env = build(qapp, theme, tmp_path, configured=False)
    assert env.term.mode() is InputMode.MANUAL
    env.term.set_mode(InputMode.PICKER)  # refused: the list needs the roster client
    assert env.term.mode() is InputMode.MANUAL
