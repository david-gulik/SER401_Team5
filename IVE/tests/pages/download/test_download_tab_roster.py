"""DownloadTab wiring for the myASU Section InputModeToggle (SCRUM-239).

Drives the real tab and view model against in-memory clients, offscreen.
Download actions are never triggered here: they end in a modal dialog.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QThreadPool

from GAVEL.app.dtos.roster import ClassSection, TermInfo
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import DownloadViewModel
from GAVEL.services.logger import AppLogger
from GAVEL.ui_components.input_mode_toggle import InputMode
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

TERMS = [TermInfo("2267", "Fall 2026", default=True)]
FIRST = ClassSection("12345", "SER", "401", "Capstone I", "Gary", "TTh 1:30")
SECOND = ClassSection("12346", "SER", "401", "Capstone I", "Ruben", "MW 3:00")
TYPED = "99999"


def pump(qapp) -> None:
    for _ in range(5):
        qapp.processEvents()


def wait_for_workers(qapp) -> None:
    assert QThreadPool.globalInstance().waitForDone(5000)
    pump(qapp)


def build(qapp, theme, tmp_path: Path, configured: bool = True) -> SimpleNamespace:
    roster = FakeRosterClient(terms=TERMS, sections=[FIRST, SECOND], configured=configured)
    vm = DownloadViewModel(
        roster_client=roster,
        canvas_client=FakeCanvasClient(),
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=configured,
    )
    tab = DownloadTab(theme, vm)
    pump(qapp)
    return SimpleNamespace(tab=tab, vm=vm, roster=roster, section=tab.section_input)


@pytest.fixture
def env(qapp, theme, tmp_path: Path, monkeypatch) -> SimpleNamespace:
    monkeypatch.delenv("CANVAS_TOKEN", raising=False)  # keep Canvas out of these tests
    return build(qapp, theme, tmp_path)


def class_number(env) -> str:
    return env.vm.get_state().class_number


def search(env, qapp, subject: str = "SER", catalog: str = "401") -> None:
    picker = env.section.picker()
    picker.subject_field.setText(subject)
    picker.catalog_field.setText(catalog)
    picker.find_button.click()
    wait_for_workers(qapp)


def test_only_one_section_input_is_visible_at_a_time(env):
    section = env.section
    assert section.mode() is InputMode.PICKER
    assert section.picker().isVisibleTo(section)
    assert not section.manual_field().isVisibleTo(section)
    section.set_mode(InputMode.MANUAL)
    assert not section.picker().isVisibleTo(section)
    assert section.manual_field().isVisibleTo(section)


def test_search_selects_first_result_and_enables_roster_download(qapp, env):
    env.vm.set_term("2267")
    assert not env.tab._download_roster_btn.isEnabled()

    search(qapp=qapp, env=env)
    assert env.roster.section_queries == [("2267", "SER", "401")]
    assert env.section.picker().combo.count() == 2
    assert class_number(env) == FIRST.class_number
    assert env.section.readout_text() == FIRST.display_label
    assert env.tab._download_roster_btn.isEnabled()


def test_picking_another_result_changes_the_class_number(qapp, env):
    env.vm.set_term("2267")
    search(qapp=qapp, env=env)
    env.section.picker().combo.setCurrentIndex(1)
    assert class_number(env) == SECOND.class_number


def test_manual_class_number_enables_roster_download(env):
    env.vm.set_term("2267")
    env.section.set_mode(InputMode.MANUAL)
    env.section.manual_field().setText(TYPED)
    assert class_number(env) == TYPED
    assert env.tab._download_roster_btn.isEnabled()


def test_invalid_manual_class_number_blocks_roster_download(env):
    env.vm.set_term("2267")
    env.section.set_mode(InputMode.MANUAL)
    env.section.manual_field().setText("abc")
    assert not env.section.is_valid()
    assert class_number(env) == ""
    assert not env.tab._download_roster_btn.isEnabled()


def test_switching_modes_swaps_the_resolved_class_number(qapp, env):
    env.vm.set_term("2267")
    search(qapp=qapp, env=env)
    env.section.set_mode(InputMode.MANUAL)
    env.section.manual_field().setText(TYPED)
    assert class_number(env) == TYPED
    env.section.set_mode(InputMode.PICKER)
    assert class_number(env) == FIRST.class_number


def test_unconfigured_roster_shows_warning_and_disables_roster_actions(
    qapp, theme, tmp_path: Path, monkeypatch
):
    monkeypatch.delenv("CANVAS_TOKEN", raising=False)
    env = build(qapp, theme, tmp_path, configured=False)
    assert env.tab._roster_warning.isVisibleTo(env.tab)
    assert env.section.mode() is InputMode.MANUAL
    assert not env.tab._load_terms_btn.isEnabled()
    env.section.set_mode(InputMode.PICKER)  # refused: search needs the roster client
    assert env.section.mode() is InputMode.MANUAL

    env.vm.set_term("2267")
    env.section.manual_field().setText(TYPED)
    assert not env.tab._download_roster_btn.isEnabled()
