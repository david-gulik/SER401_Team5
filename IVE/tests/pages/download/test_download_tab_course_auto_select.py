"""DownloadTab pre-selects the Canvas course that matches the roster class."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection, TermInfo
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import DownloadViewModel
from GAVEL.services.logger import AppLogger
from GAVEL.ui_components.input_mode_toggle import InputMode
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_viewmodel_roster import wait_for_workers

TERMS = [TermInfo("2267", "Fall 2026", default=True)]
SECTIONS = [
    ClassSection("87275", "SER", "402", "Computing Capstone II", "Acuna", "TTh 12:00"),
    ClassSection("12345", "SER", "402", "Computing Capstone II", "Gary", "MW 3:00"),
]
# Sorted by course code, so CSE 110 lands first and is selected when the list fills.
CSE110 = CanvasCourse(id=270001, name="CSE 110", course_code="2026FallC-X-CSE110-11111")
SER402 = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")
SANDBOX = CanvasCourse(id=253450, name="Sandbox", course_code="TRN-2026Spring-ivecapstone")


def pump(qapp) -> None:
    for _ in range(5):
        qapp.processEvents()


@pytest.fixture
def env(qapp, theme, tmp_path: Path, monkeypatch) -> SimpleNamespace:
    monkeypatch.setenv("CANVAS_TOKEN", "test-token")
    canvas = FakeCanvasClient(courses=[SER402, CSE110, SANDBOX])
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(terms=TERMS, sections=SECTIONS),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    tab = DownloadTab(theme, vm)
    pump(qapp)
    vm.set_term("2267")
    return SimpleNamespace(tab=tab, vm=vm, canvas=canvas, banner=tab.section_warning_label)


def search(env, qapp) -> None:
    """Search sections; the picker selects the first one (87275) when filled."""
    env.vm.set_subject("SER")
    env.vm.set_catalog_number("402")
    env.vm.find_sections()
    wait_for_workers(qapp)


def type_class_number(env, text: str) -> None:
    env.tab.section_input.set_mode(InputMode.MANUAL)
    env.tab.section_input.manual_field().setText(text)


def selected_course(env) -> str:
    return env.vm.get_state().selected_course_id


def test_course_list_starts_on_its_first_course(env):
    assert selected_course(env) == str(CSE110.id)


def test_searched_section_selects_its_canvas_course(qapp, env):
    search(env, qapp)
    assert env.vm.get_state().class_number == "87275"
    assert selected_course(env) == str(SER402.id)
    assert env.tab.course_input.value() == str(SER402.id)
    assert not env.banner.isVisibleTo(env.tab)


def test_auto_selected_course_loads_its_quizzes_and_assignments(qapp, env):
    search(env, qapp)
    assert env.canvas.quiz_calls[-1] == SER402.id
    assert env.canvas.assignment_calls[-1] == SER402.id


def test_typed_class_number_selects_its_canvas_course(env):
    type_class_number(env, "87275")
    assert selected_course(env) == str(SER402.id)


def test_no_match_leaves_the_course_alone_and_keeps_the_banner(env):
    type_class_number(env, "12345")
    assert selected_course(env) == str(CSE110.id)
    assert env.banner.isVisibleTo(env.tab)
    assert "class 12345" in env.banner.text()


def test_course_can_still_be_changed_by_hand_after_auto_select(qapp, env):
    search(env, qapp)
    assert selected_course(env) == str(SER402.id)

    combo = env.tab.course_input.picker().combo
    combo.setCurrentIndex(combo.findData(str(SANDBOX.id)))
    pump(qapp)
    assert selected_course(env) == str(SANDBOX.id)

    # Picking a class with no course of its own keeps the user's choice.
    env.tab.section_input.picker().combo.setCurrentIndex(1)  # class 12345
    assert selected_course(env) == str(SANDBOX.id)


def test_typed_course_id_is_never_replaced(qapp, env):
    env.tab.course_input.set_mode(InputMode.MANUAL)
    env.tab.course_input.manual_field().setText("999999")
    search(env, qapp)
    assert env.tab.course_input.mode() is InputMode.MANUAL
    assert selected_course(env) == "999999"
