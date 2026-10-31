"""Completed-download tracking in DownloadViewModel."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse, CanvasQuiz
from GAVEL.app.ports.canvas_client import QuizReportUnavailableError
from GAVEL.pages.download.viewmodel import (
    CANVAS_DOWNLOADS,
    CONSENT_DOWNLOAD,
    GRADEBOOK_DOWNLOAD,
    QUIZ_REPORTS_DOWNLOAD,
    ROSTER_DOWNLOAD,
    DownloadViewModel,
)
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_viewmodel_roster import wait_for_workers

COURSE = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")
OTHER = CanvasCourse(id=250417, name="SER 401", course_code="2026SpringC-X-SER401-37789")
QUIZZES = [CanvasQuiz(id=101, name="Quiz One"), CanvasQuiz(id=202, name="Quiz Two")]


class GradebookCanvasClient(FakeCanvasClient):
    """Lets the gradebook and listed quizzes' reports download; everything else still raises.

    Any quiz id in ``unavailable_quiz_ids`` has no report on Canvas.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.unavailable_quiz_ids: set[int] = set()

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        self.download_calls.append("fetch_gradebook_csv")
        return b"Student,ID\n"

    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
        if quiz_id not in {q.id for q in self.quizzes}:
            return super().fetch_quiz_student_analysis(course_id, quiz_id)
        self.download_calls.append("fetch_quiz_student_analysis")
        if quiz_id in self.unavailable_quiz_ids:
            raise QuizReportUnavailableError("No report available")
        return b"student,score\n"


@pytest.fixture
def canvas() -> GradebookCanvasClient:
    return GradebookCanvasClient(courses=[COURSE, OTHER], quizzes=QUIZZES)


@pytest.fixture
def vm(qapp, canvas: GradebookCanvasClient, tmp_path: Path) -> DownloadViewModel:
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    vm.load_courses()
    vm.set_course_id(str(COURSE.id))
    return vm


def test_nothing_is_completed_at_first(vm):
    assert vm.get_state().completed == frozenset()
    assert not vm.get_state().canvas_downloads_partial


def test_successful_gradebook_download_is_recorded(vm):
    vm.download_gradebook()
    state = vm.get_state()
    assert state.completed == {GRADEBOOK_DOWNLOAD}
    assert state.canvas_downloads_partial


def test_successful_quiz_reports_download_is_recorded(qapp, vm):
    vm.download_all_quizzes()
    wait_for_workers(qapp)
    state = vm.get_state()
    assert state.completed == {QUIZ_REPORTS_DOWNLOAD}
    assert "2 saved" in state.message


def test_quiz_reports_already_in_the_folder_still_count_as_done(qapp, vm):
    vm.download_all_quizzes()
    wait_for_workers(qapp)
    # Leaving and coming back forgets the mark; the CSVs stay in the folder.
    vm.set_course_id(str(OTHER.id))
    vm.set_course_id(str(COURSE.id))
    assert vm.get_state().completed == frozenset()

    vm.download_all_quizzes()
    wait_for_workers(qapp)

    state = vm.get_state()
    assert state.completed == {QUIZ_REPORTS_DOWNLOAD}
    assert "0 saved" in state.message and "2 already downloaded" in state.message


def test_quiz_reports_with_no_report_on_canvas_are_not_recorded(qapp, vm, canvas):
    canvas.unavailable_quiz_ids = {q.id for q in QUIZZES}
    vm.download_all_quizzes()
    wait_for_workers(qapp)
    state = vm.get_state()
    assert state.completed == frozenset()
    assert "0 already downloaded, 2 skipped" in state.message


def test_download_all_includes_quiz_reports(qapp, vm, monkeypatch):
    # Without credentials the Gradescope step fails fast instead of opening a browser.
    monkeypatch.delenv("CANVAS_USERNAME", raising=False)
    monkeypatch.delenv("CANVAS_PASSWORD", raising=False)
    vm.set_term("2267")
    vm.set_class_number("87275")
    vm.set_consent_quiz_id("11")  # the fake raises on consent; the batch carries on
    vm.download_all()
    wait_for_workers(qapp)

    state = vm.get_state()
    assert QUIZ_REPORTS_DOWNLOAD in state.completed
    for quiz in QUIZZES:
        assert f"{QUIZ_REPORTS_DOWNLOAD} ({quiz.name})" in state.message


def test_changing_the_course_forgets_quiz_reports(qapp, vm):
    vm.download_all_quizzes()
    wait_for_workers(qapp)
    vm.set_course_id(str(OTHER.id))
    assert QUIZ_REPORTS_DOWNLOAD not in vm.get_state().completed


def test_failed_download_is_not_recorded(vm):
    vm.set_consent_quiz_id("11")
    vm.download_consent()  # the fake raises on fetch
    assert vm.get_state().completed == frozenset()


def test_successful_roster_download_is_recorded(qapp, vm):
    vm.set_term("2267")
    vm.set_class_number("87275")
    vm.download_roster()
    wait_for_workers(qapp)
    assert vm.get_state().completed == {ROSTER_DOWNLOAD}
    assert not vm.get_state().canvas_downloads_partial  # roster is not a Canvas download


def test_changing_the_course_forgets_canvas_downloads_only(qapp, vm):
    vm.set_term("2267")
    vm.set_class_number("87275")
    vm.download_roster()
    wait_for_workers(qapp)
    vm.download_gradebook()
    assert vm.get_state().completed == {ROSTER_DOWNLOAD, GRADEBOOK_DOWNLOAD}

    vm.set_course_id(str(OTHER.id))
    assert vm.get_state().completed == {ROSTER_DOWNLOAD}


def test_changing_the_class_number_or_term_forgets_the_roster_only(qapp, vm):
    vm.set_term("2267")
    vm.set_class_number("87275")
    vm.download_roster()
    wait_for_workers(qapp)
    vm.download_gradebook()

    vm.set_class_number("12345")
    assert vm.get_state().completed == {GRADEBOOK_DOWNLOAD}

    vm.download_roster()
    wait_for_workers(qapp)
    vm.set_term("2261")
    assert vm.get_state().completed == {GRADEBOOK_DOWNLOAD}


def test_reselecting_the_same_course_keeps_completion(vm):
    vm.download_gradebook()
    vm.set_course_id(str(COURSE.id))
    assert GRADEBOOK_DOWNLOAD in vm.get_state().completed


def test_partial_means_some_but_not_all_canvas_downloads(vm):
    state = vm.get_state()
    assert not replace(state, completed=frozenset()).canvas_downloads_partial
    assert replace(state, completed=frozenset({CONSENT_DOWNLOAD})).canvas_downloads_partial
    assert not replace(state, completed=CANVAS_DOWNLOADS).canvas_downloads_partial
