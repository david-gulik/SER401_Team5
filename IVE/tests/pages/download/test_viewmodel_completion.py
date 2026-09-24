"""Completed-download tracking in DownloadViewModel."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.pages.download.viewmodel import (
    CANVAS_DOWNLOADS,
    CONSENT_DOWNLOAD,
    GRADEBOOK_DOWNLOAD,
    ROSTER_DOWNLOAD,
    DownloadViewModel,
)
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_viewmodel_roster import wait_for_workers

COURSE = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")
OTHER = CanvasCourse(id=250417, name="SER 401", course_code="2026SpringC-X-SER401-37789")


class GradebookCanvasClient(FakeCanvasClient):
    """Lets the gradebook download succeed; everything else still raises."""

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        self.download_calls.append("fetch_gradebook_csv")
        return b"Student,ID\n"


@pytest.fixture
def vm(qapp, tmp_path: Path) -> DownloadViewModel:
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=GradebookCanvasClient(courses=[COURSE, OTHER]),
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
