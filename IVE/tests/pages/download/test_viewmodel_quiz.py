"""Consent quiz resolution in DownloadViewModel: one id for the consent download and Download All."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasQuiz
from GAVEL.core.status import Status
from GAVEL.pages.download.viewmodel import DownloadViewModel, ShowError, quiz_id_error
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

QUIZZES = [CanvasQuiz(id=5, name="Attendance Quiz"), CanvasQuiz(id=11, name="Research Consent")]


@pytest.fixture
def canvas() -> FakeCanvasClient:
    return FakeCanvasClient(quizzes=QUIZZES)


@pytest.fixture
def vm(qapp, canvas: FakeCanvasClient, tmp_path: Path) -> DownloadViewModel:
    return DownloadViewModel(
        roster_client=FakeRosterClient(),
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
    [("1234567", True), ("0", True), ("", False), ("abc", False), ("12 34", False), ("12a", False)],
)
def test_quiz_id_error_accepts_digits_only(text: str, usable: bool):
    assert (quiz_id_error(text) is None) is usable


def test_consent_download_requires_a_quiz_after_the_course(vm, canvas):
    vm.set_course_id("213877")
    seen = events(vm)
    vm.download_consent()
    assert seen == [ShowError("Select a consent quiz first.")]
    assert canvas.download_calls == []


def test_consent_download_rejects_a_non_numeric_quiz_id(vm, canvas):
    vm.set_course_id("213877")
    vm.set_consent_quiz_id("abc")
    seen = events(vm)
    vm.download_consent()
    assert len(seen) == 1 and isinstance(seen[0], ShowError)
    assert "'abc'" in seen[0].message and "numbers only" in seen[0].message
    assert vm.get_state().status is Status.CRITICAL
    assert canvas.download_calls == []


def test_download_all_reads_the_same_resolved_quiz_id(vm, canvas):
    vm.set_term("2267")
    vm.set_class_number("12345")
    vm.set_course_id("213877")
    vm.set_consent_quiz_id("abc")
    assert vm.get_state().can_download_all
    seen = events(vm)
    vm.download_all()
    assert len(seen) == 1 and isinstance(seen[0], ShowError)
    assert "quiz ID" in seen[0].message and "numbers only" in seen[0].message
    assert canvas.download_calls == []


def test_changing_course_clears_the_quiz_choice(vm):
    vm.set_course_id("213877")
    vm.load_quizzes("213877")
    vm.set_consent_quiz_id("11")
    assert vm.get_state().can_download_consent
    vm.set_course_id("209555")
    state = vm.get_state()
    assert state.quizzes == ()
    assert state.selected_consent_quiz_id == ""
    assert not state.can_download_consent
