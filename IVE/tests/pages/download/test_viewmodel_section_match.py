"""DownloadUiState derives the roster/Canvas mismatch warning from its own selections."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection, TermInfo
from GAVEL.pages.download.viewmodel import DownloadViewModel
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_viewmodel_roster import wait_for_workers

TERMS = [TermInfo("2267", "Fall 2026", default=True)]
SECTIONS = [
    ClassSection("87275", "SER", "402", "Computing Capstone II", "Acuna", "TTh 12:00"),
    ClassSection("12345", "SER", "402", "Computing Capstone II", "Gary", "MW 3:00"),
]
SER402 = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")
SANDBOX = CanvasCourse(id=253450, name="Sandbox", course_code="TRN-2026Spring-ivecapstone")


@pytest.fixture
def vm(qapp, tmp_path: Path) -> DownloadViewModel:
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(terms=TERMS, sections=SECTIONS),
        canvas_client=FakeCanvasClient(courses=[SER402, SANDBOX]),
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    vm.load_courses()
    vm.set_term("2267")
    vm.set_subject("SER")
    vm.set_catalog_number("402")
    vm.find_sections()
    wait_for_workers(qapp)
    return vm


def test_selected_course_and_section_resolve_from_ids(vm):
    vm.set_course_id(str(SER402.id))
    vm.set_class_number("87275")
    state = vm.get_state()
    assert state.selected_course == SER402
    assert state.selected_section == SECTIONS[0]


def test_typed_ids_resolve_to_none(vm):
    vm.set_course_id("999999")
    vm.set_class_number("55555")
    state = vm.get_state()
    assert state.selected_course is None
    assert state.selected_section is None
    assert state.section_warning is None


def test_matching_selections_raise_no_warning(vm):
    vm.set_course_id(str(SER402.id))
    vm.set_class_number("87275")
    assert vm.get_state().section_warning is None


def test_mismatched_selections_raise_the_warning(vm):
    vm.set_course_id(str(SER402.id))
    vm.set_class_number("12345")
    text = vm.get_state().section_warning
    assert text is not None
    assert "SER 402 class 12345" in text
    assert "2026FallC-X-SER402-87275" in text


def test_typed_class_number_is_still_checked(vm):
    vm.set_course_id(str(SER402.id))
    vm.set_class_number("55555")  # not one of the searched sections
    text = vm.get_state().section_warning
    assert text is not None and "class 55555" in text


def test_sandbox_course_never_warns(vm):
    vm.set_course_id(str(SANDBOX.id))
    vm.set_class_number("12345")
    assert vm.get_state().section_warning is None


def test_warning_clears_when_the_course_changes_to_match(vm):
    vm.set_course_id(str(SANDBOX.id))
    vm.set_class_number("87275")
    vm.set_course_id(str(SER402.id))
    assert vm.get_state().section_warning is None
