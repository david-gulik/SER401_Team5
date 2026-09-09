"""Term resolution in DownloadViewModel: one term code for search, roster, and Download All."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QThreadPool

from GAVEL.app.dtos.roster import TermInfo
from GAVEL.core.status import Status
from GAVEL.pages.download.viewmodel import DownloadViewModel, ShowError, term_code_error
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

TERMS = [
    TermInfo("2261", "Spring 2026"),
    TermInfo("2267", "Fall 2026", default=True),
    TermInfo("2271", "Spring 2027"),
]


def wait_for_workers(qapp) -> None:
    assert QThreadPool.globalInstance().waitForDone(5000)
    for _ in range(5):
        qapp.processEvents()


@pytest.fixture
def roster() -> FakeRosterClient:
    return FakeRosterClient(terms=TERMS)


@pytest.fixture
def canvas() -> FakeCanvasClient:
    return FakeCanvasClient()


@pytest.fixture
def vm(qapp, roster, canvas, tmp_path: Path) -> DownloadViewModel:
    return DownloadViewModel(
        roster_client=roster,
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )


def events(vm: DownloadViewModel) -> list:
    seen: list = []
    vm.event_raised.connect(seen.append)
    return seen


@pytest.mark.parametrize(
    ("text", "usable"),
    [
        ("2267", True),  # Fall 2026
        ("2261", True),  # Spring 2026
        ("2264", True),  # Summer 2026
        ("2269", True),  # Winter 2026
        ("", False),
        ("226", False),
        ("22677", False),
        ("1267", False),  # must start with 2
        ("2262", False),  # 2 is not a semester digit
        ("22F7", False),
        ("abcd", False),
    ],
)
def test_term_code_error_enforces_2yyt_format(text: str, usable: bool):
    assert (term_code_error(text) is None) is usable


def test_load_terms_publishes_the_list_and_preselects_the_default(qapp, vm):
    vm.load_terms()
    wait_for_workers(qapp)
    state = vm.get_state()
    assert [t.code for t in state.terms] == ["2261", "2267", "2271"]
    assert state.selected_term == "2267"
    assert state.status is Status.NOMINAL


def test_section_search_requires_a_term(vm, roster):
    vm.set_subject("SER")
    vm.set_catalog_number("401")
    seen = events(vm)
    vm.find_sections()
    assert seen == [ShowError("Select a term first.")]
    assert roster.section_queries == []


def test_section_search_rejects_a_malformed_term(vm, roster):
    vm.set_term("22F7")
    vm.set_subject("SER")
    vm.set_catalog_number("401")
    seen = events(vm)
    vm.find_sections()
    assert len(seen) == 1 and isinstance(seen[0], ShowError)
    assert "'22F7'" in seen[0].message and "look like 2267" in seen[0].message
    assert roster.section_queries == []


def test_roster_download_rejects_a_malformed_term_before_the_class_number(vm, roster):
    vm.set_term("1267")
    vm.set_class_number("abc")  # would also fail, but the term is checked first
    seen = events(vm)
    vm.download_roster()
    assert len(seen) == 1 and isinstance(seen[0], ShowError)
    assert "term code" in seen[0].message
    assert vm.get_state().status is Status.CRITICAL
    assert roster.roster_requests == []


def test_download_all_reads_the_same_resolved_term(vm, roster, canvas):
    vm.set_term("2262")
    vm.set_class_number("12345")
    vm.set_course_id("213877")
    vm.set_consent_quiz_id("11")
    assert vm.get_state().can_download_all
    seen = events(vm)
    vm.download_all()
    assert len(seen) == 1 and isinstance(seen[0], ShowError)
    assert "term code" in seen[0].message
    assert roster.roster_requests == [] and canvas.download_calls == []
