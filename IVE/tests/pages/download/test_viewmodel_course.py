"""Course resolution in DownloadViewModel: one canonical id for every Canvas download."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasCourse, CanvasQuiz
from GAVEL.core.status import Status
from GAVEL.pages.download.viewmodel import DownloadViewModel, ShowError, course_id_error
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

COURSES = [
    CanvasCourse(id=213877, name="Capstone I", course_code="SER401"),
    CanvasCourse(id=209555, name="Operating Systems", course_code="SER334"),
]
QUIZZES = [CanvasQuiz(id=11, name="Consent Quiz")]
ASSIGNMENTS = [CanvasAssignment(id=7, name="Homework 1")]

# Every single-item Canvas download entry point on the view model.
CANVAS_DOWNLOADS = [
    "download_gradebook",
    "download_gradescope_submissions",
    "download_consent",
    "download_rubric_assessment",
    "download_all_rubric_assessments",
]


@pytest.fixture
def canvas() -> FakeCanvasClient:
    return FakeCanvasClient(courses=COURSES, quizzes=QUIZZES, assignments=ASSIGNMENTS)


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
    [
        ("213877", True),
        ("0", True),
        ("", False),
        ("abc", False),
        ("21 3877", False),
        ("-1", False),
        ("213877x", False),
    ],
)
def test_course_id_error_accepts_digits_only(text: str, usable: bool):
    assert (course_id_error(text) is None) is usable


@pytest.mark.parametrize("method", CANVAS_DOWNLOADS)
def test_downloads_refuse_when_no_course_selected(vm, canvas, method):
    seen = events(vm)
    getattr(vm, method)()
    assert seen == [ShowError("Select a course first.")]
    assert vm.get_state().status is Status.CRITICAL
    assert canvas.download_calls == []


@pytest.mark.parametrize("method", CANVAS_DOWNLOADS)
def test_downloads_refuse_non_numeric_course_before_starting(vm, canvas, method):
    vm.set_course_id("abc")
    vm.set_consent_quiz_id("11")
    vm.set_assignment_id("7")
    seen = events(vm)
    getattr(vm, method)()
    assert len(seen) == 1
    assert isinstance(seen[0], ShowError)
    assert "'abc'" in seen[0].message
    assert "numbers only" in seen[0].message
    assert vm.get_state().status is Status.CRITICAL
    assert canvas.download_calls == []


def test_download_all_refuses_non_numeric_course(vm, canvas):
    vm.set_term("2267")
    vm.set_class_number("12345")
    vm.set_course_id("abc")
    vm.set_consent_quiz_id("11")
    assert vm.get_state().can_download_all
    seen = events(vm)
    vm.download_all()
    assert len(seen) == 1
    assert isinstance(seen[0], ShowError)
    assert "numbers only" in seen[0].message
    assert canvas.download_calls == []


def test_consent_checks_quiz_only_after_course_is_valid(vm):
    vm.set_course_id("213877")
    seen = events(vm)
    vm.download_consent()
    assert seen == [ShowError("Select a consent quiz first.")]


def test_rubric_checks_assignment_only_after_course_is_valid(vm):
    vm.set_course_id("213877")
    seen = events(vm)
    vm.download_rubric_assessment()
    assert seen == [ShowError("Enter an assignment ID first.")]


def test_set_course_id_resets_dependents_only_when_the_id_changes(vm):
    vm.set_course_id("213877")
    vm.load_quizzes("213877")
    vm.load_assignments("213877")
    vm.set_consent_quiz_id("11")
    vm.set_assignment_id("7")

    vm.set_course_id(" 213877 ")  # same id, only whitespace differs
    state = vm.get_state()
    assert state.selected_course_id == "213877"
    assert state.quizzes and state.assignments
    assert state.selected_consent_quiz_id == "11"

    vm.set_course_id("209555")
    state = vm.get_state()
    assert state.selected_course_id == "209555"
    assert state.quizzes == () and state.assignments == ()
    assert state.selected_consent_quiz_id == "" and state.assignment_id == ""
