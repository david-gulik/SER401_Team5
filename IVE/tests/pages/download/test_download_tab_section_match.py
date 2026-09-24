"""DownloadTab shows the roster/Canvas mismatch banner without blocking anything."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection, TermInfo
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import DownloadViewModel
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_viewmodel_roster import wait_for_workers

TERMS = [TermInfo("2267", "Fall 2026", default=True)]
SECTIONS = [
    ClassSection("87275", "SER", "402", "Computing Capstone II", "Acuna", "TTh 12:00"),
    ClassSection("12345", "SER", "402", "Computing Capstone II", "Gary", "MW 3:00"),
]
# Sorted by course code, so the SER 402 course lands first and is auto-selected.
SER402 = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")
SANDBOX = CanvasCourse(id=253450, name="Sandbox", course_code="TRN-2026Spring-ivecapstone")


def pump(qapp) -> None:
    for _ in range(5):
        qapp.processEvents()


@pytest.fixture
def env(qapp, theme, tmp_path: Path, monkeypatch) -> SimpleNamespace:
    monkeypatch.setenv("CANVAS_TOKEN", "test-token")
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(terms=TERMS, sections=SECTIONS),
        canvas_client=FakeCanvasClient(courses=[SER402, SANDBOX]),
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    tab = DownloadTab(theme, vm)
    pump(qapp)
    # Search sections; the picker selects the first one (87275) when filled.
    vm.set_term("2267")
    vm.set_subject("SER")
    vm.set_catalog_number("402")
    vm.find_sections()
    wait_for_workers(qapp)
    return SimpleNamespace(tab=tab, vm=vm, banner=tab.section_warning_label)


def test_matching_selections_show_no_banner(env):
    state = env.vm.get_state()
    assert state.selected_course_id == str(SER402.id)
    assert state.class_number == "87275"
    assert not env.banner.isVisibleTo(env.tab)


def test_mismatched_section_shows_the_banner_and_keeps_downloads_enabled(env):
    env.tab.section_input.picker().combo.setCurrentIndex(1)  # class 12345
    assert env.banner.isVisibleTo(env.tab)
    assert "class 12345" in env.banner.text()
    assert "2026FallC-X-SER402-87275" in env.banner.text()
    assert env.tab._download_gradebook_btn.isEnabled()
    assert env.tab._download_roster_btn.isEnabled()


def test_banner_clears_when_selections_agree_again(env):
    env.tab.section_input.picker().combo.setCurrentIndex(1)
    assert env.banner.isVisibleTo(env.tab)
    env.tab.section_input.picker().combo.setCurrentIndex(0)
    assert not env.banner.isVisibleTo(env.tab)


def test_sandbox_course_shows_no_banner(env):
    env.tab.section_input.picker().combo.setCurrentIndex(1)
    env.tab.course_input.picker().combo.setCurrentIndex(1)  # the TRN sandbox
    assert not env.banner.isVisibleTo(env.tab)
