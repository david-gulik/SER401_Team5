"""Class number resolution in DownloadViewModel: one value for roster and Download All."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QThreadPool

from GAVEL.app.dtos.roster import ClassSection, RosterRequest, TermInfo
from GAVEL.core.status import Status
from GAVEL.pages.download.viewmodel import DownloadViewModel, ShowError, class_number_error
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

TERMS = [TermInfo("2267", "Fall 2026", default=True)]
SECTIONS = [
    ClassSection("22222", "SER", "401", "Capstone I", "Ruben", "MW 3:00"),
    ClassSection("11111", "SER", "401", "Capstone I", "Gary", "TTh 1:30"),
]


def wait_for_workers(qapp) -> None:
    """Let QThreadPool jobs finish and deliver their queued signals."""
    assert QThreadPool.globalInstance().waitForDone(5000)
    for _ in range(5):
        qapp.processEvents()


@pytest.fixture
def roster() -> FakeRosterClient:
    return FakeRosterClient(terms=TERMS, sections=SECTIONS)


@pytest.fixture
def canvas() -> FakeCanvasClient:
    return FakeCanvasClient()


def make_vm(
    roster: FakeRosterClient, canvas: FakeCanvasClient, tmp_path: Path
) -> DownloadViewModel:
    return DownloadViewModel(
        roster_client=roster,
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=roster.is_configured,
    )


@pytest.fixture
def vm(qapp, roster, canvas, tmp_path: Path) -> DownloadViewModel:
    return make_vm(roster, canvas, tmp_path)


def events(vm: DownloadViewModel) -> list:
    seen: list = []
    vm.event_raised.connect(seen.append)
    return seen


@pytest.mark.parametrize(
    ("text", "usable"),
    [
        ("12345", True),
        ("0", True),
        ("", False),
        ("abc", False),
        ("12 345", False),
        ("1234a", False),
    ],
)
def test_class_number_error_accepts_digits_only(text: str, usable: bool):
    assert (class_number_error(text) is None) is usable


def test_roster_download_requires_a_term_first(vm, roster):
    vm.set_class_number("12345")
    seen = events(vm)
    vm.download_roster()
    assert seen == [ShowError("Select a term first.")]
    assert roster.roster_requests == []


def test_roster_download_requires_a_class_number(vm, roster):
    vm.set_term("2267")
    seen = events(vm)
    vm.download_roster()
    assert seen == [ShowError("Search for a section or enter a class number first.")]
    assert roster.roster_requests == []


def test_roster_download_rejects_non_numeric_class_number(vm, roster):
    vm.set_term("2267")
    vm.set_class_number("abc")
    seen = events(vm)
    vm.download_roster()
    assert len(seen) == 1 and isinstance(seen[0], ShowError)
    assert "'abc'" in seen[0].message and "numbers only" in seen[0].message
    assert vm.get_state().status is Status.CRITICAL
    assert roster.roster_requests == []


def test_roster_download_uses_the_resolved_class_number(qapp, vm, roster, tmp_path: Path):
    vm.set_term("2267")
    vm.set_class_number("12345")
    vm.download_roster()
    wait_for_workers(qapp)

    assert roster.roster_requests == [RosterRequest(term="2267", class_number="12345")]
    assert roster.authenticate_calls == 1 and roster.close_calls == 1
    state = vm.get_state()
    assert state.status is Status.NOMINAL
    assert state.last_saved_path == str(tmp_path / "roster_2267_12345.csv")
    assert Path(state.last_saved_path).read_text(encoding="utf-8").startswith("Student,ID\n")


def test_find_sections_publishes_sorted_results_without_choosing_one(qapp, vm, roster):
    vm.set_term("2267")
    vm.set_subject("ser")
    vm.set_catalog_number("401")
    vm.find_sections()
    wait_for_workers(qapp)

    assert roster.section_queries == [("2267", "SER", "401")]
    state = vm.get_state()
    assert [s.class_number for s in state.sections] == ["22222", "11111"]  # stable sort
    assert state.class_number == ""  # the picker, not the view model, chooses


def test_download_all_reads_the_same_resolved_class_number(vm, roster, canvas):
    vm.set_term("2267")
    vm.set_class_number("abc")
    vm.set_course_id("213877")
    vm.set_consent_quiz_id("11")
    assert vm.get_state().can_download_all
    seen = events(vm)
    vm.download_all()
    assert len(seen) == 1 and isinstance(seen[0], ShowError)
    assert "class number" in seen[0].message and "numbers only" in seen[0].message
    assert roster.roster_requests == [] and canvas.download_calls == []


def test_unconfigured_roster_is_reported_not_swallowed(qapp, canvas, tmp_path: Path):
    roster = FakeRosterClient(configured=False)
    vm = make_vm(roster, canvas, tmp_path)
    state = vm.get_state()
    assert state.roster_configured is False
    assert state.status is Status.CRITICAL
    assert state.message == "Roster not configured"

    vm.set_term("2267")
    vm.set_class_number("12345")
    assert not vm.get_state().can_download_roster

    seen = events(vm)
    vm.load_terms()
    vm.find_sections()
    vm.download_roster()
    assert len(seen) == 3
    assert all(isinstance(e, ShowError) and "not configured" in e.message for e in seen)
    assert roster.roster_requests == []
