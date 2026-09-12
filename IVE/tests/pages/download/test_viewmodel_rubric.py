"""Rubric assignment resolution in DownloadViewModel: one download per listed assignment."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.core.status import Status
from GAVEL.pages.download.viewmodel import (
    DownloadViewModel,
    ShowError,
    ShowInfo,
    assignment_ids_error,
    parse_assignment_ids,
)
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

COURSE_ID = "213877"
ASSIGNMENTS = [CanvasAssignment(id=7, name="Homework 1"), CanvasAssignment(id=9, name="Project")]
NO_RUBRIC = CanvasAssignment(id=12, name="Quiz 3", has_rubric=False)


class RubricCanvasClient(FakeCanvasClient):
    """Serves empty rubric data and records which assignments were fetched.

    Any assignment id in ``failing`` raises instead, so partial failures can
    be exercised.
    """

    def __init__(
        self,
        failing: set[int] = frozenset(),
        assignments: list[CanvasAssignment] = ASSIGNMENTS,
    ) -> None:
        super().__init__(assignments=assignments)
        self.failing = set(failing)
        self.rubric_calls: list[int] = []

    def fetch_rubric_assessments(
        self, course_id: int, assignment_id: int
    ) -> list[RubricAssessment]:
        self.rubric_calls.append(assignment_id)
        if assignment_id in self.failing:
            raise RuntimeError(f"no rubric on {assignment_id}")
        return []

    def fetch_rubric_definition(
        self, course_id: int, assignment_id: int
    ) -> RubricDefinition | None:
        return None


@pytest.fixture
def canvas() -> RubricCanvasClient:
    return RubricCanvasClient()


def make_vm(qapp, canvas: FakeCanvasClient, tmp_path: Path) -> DownloadViewModel:
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    vm.set_course_id(COURSE_ID)
    return vm


@pytest.fixture
def vm(qapp, canvas: RubricCanvasClient, tmp_path: Path) -> DownloadViewModel:
    return make_vm(qapp, canvas, tmp_path)


def events(vm: DownloadViewModel) -> list:
    seen: list = []
    vm.event_raised.connect(seen.append)
    return seen


@pytest.mark.parametrize(
    ("text", "usable"),
    [
        ("7216983", True),
        ("7216983,7216990", True),
        ("7216983, 7216990", True),
        ("0", True),
        ("", False),
        ("abc", False),
        ("7216983, abc", False),
        ("7216983,", False),
        (",7216983", False),
        ("7216983 7216990", False),
    ],
)
def test_assignment_ids_error_accepts_comma_separated_digits_only(text: str, usable: bool):
    assert (assignment_ids_error(text) is None) is usable


def test_parse_assignment_ids_keeps_order_and_drops_duplicates():
    assert parse_assignment_ids("9, 7,9 ,7") == [9, 7]


def test_rubric_download_requires_an_assignment_after_the_course(vm, canvas):
    seen = events(vm)
    vm.download_rubric_assessment()
    assert seen == [ShowError("Select or enter at least one assignment first.")]
    assert canvas.rubric_calls == []


def test_rubric_download_rejects_non_numeric_assignment_ids(vm, canvas):
    vm.set_assignment_ids("7, abc")
    seen = events(vm)
    vm.download_rubric_assessment()
    assert len(seen) == 1 and isinstance(seen[0], ShowError)
    assert "'7, abc'" in seen[0].message and "numbers only" in seen[0].message
    assert vm.get_state().status is Status.CRITICAL
    assert canvas.rubric_calls == []


def test_single_assignment_download_keeps_the_use_case_message(vm, canvas, tmp_path):
    vm.set_assignment_ids("7")
    seen = events(vm)
    vm.download_rubric_assessment()
    assert canvas.rubric_calls == [7]
    state = vm.get_state()
    assert state.status is Status.NOMINAL
    assert (tmp_path / "rubric_assessment_213877_7.json").exists()
    assert state.last_saved_path == str(tmp_path / "rubric_assessment_213877_7.json")
    assert seen == [ShowInfo(state.message)]
    assert "assignment 7" in state.message


def test_multiple_assignments_download_one_file_each(vm, canvas, tmp_path):
    vm.set_assignment_ids("9, 7")
    seen = events(vm)
    vm.download_rubric_assessment()
    assert canvas.rubric_calls == [9, 7]
    assert (tmp_path / "rubric_assessment_213877_9.json").exists()
    assert (tmp_path / "rubric_assessment_213877_7.json").exists()
    state = vm.get_state()
    assert state.status is Status.NOMINAL
    assert state.message == "Rubric assessments for course 213877: 2 saved, 0 failed."
    assert state.last_saved_path == str(tmp_path / "rubric_assessment_213877_7.json")
    assert seen == [ShowInfo(state.message)]


def test_one_failing_assignment_does_not_stop_the_others(qapp, tmp_path):
    canvas = RubricCanvasClient(failing={9})
    vm = make_vm(qapp, canvas, tmp_path)
    vm.set_assignment_ids("9, 7")
    seen = events(vm)
    vm.download_rubric_assessment()
    assert canvas.rubric_calls == [9, 7]
    state = vm.get_state()
    assert state.status is Status.WARNING
    assert state.message.startswith("Rubric assessments for course 213877: 1 saved, 1 failed.")
    assert "9: no rubric on 9" in state.message
    assert state.last_saved_path == str(tmp_path / "rubric_assessment_213877_7.json")
    assert seen == [ShowError(state.message)]


def test_every_assignment_failing_is_critical(qapp, tmp_path):
    canvas = RubricCanvasClient(failing={7, 9})
    vm = make_vm(qapp, canvas, tmp_path)
    vm.set_assignment_ids("7,9")
    seen = events(vm)
    vm.download_rubric_assessment()
    state = vm.get_state()
    assert state.status is Status.CRITICAL
    assert state.message == "7: no rubric on 7; 9: no rubric on 9"
    assert state.last_saved_path is None
    assert seen == [ShowError(state.message)]


def test_changing_course_clears_the_assignment_choice(vm):
    vm.load_assignments(COURSE_ID)
    vm.set_assignment_ids("7,9")
    assert vm.get_state().can_download_rubric
    vm.set_course_id("209555")
    state = vm.get_state()
    assert state.assignments == ()
    assert state.assignment_ids == ""
    assert not state.can_download_rubric


def test_loaded_assignment_without_a_rubric_is_skipped_not_fetched(qapp, tmp_path):
    canvas = RubricCanvasClient(assignments=[*ASSIGNMENTS, NO_RUBRIC])
    vm = make_vm(qapp, canvas, tmp_path)
    vm.load_assignments(COURSE_ID)
    vm.set_assignment_ids("12, 7")
    seen = events(vm)
    vm.download_rubric_assessment()
    assert canvas.rubric_calls == [7]
    state = vm.get_state()
    assert state.status is Status.WARNING
    assert state.message == (
        "Rubric assessments for course 213877: 1 saved, 1 skipped, 0 failed. "
        "Skipped: 'Quiz 3' has no rubric attached."
    )
    assert state.last_saved_path == str(tmp_path / "rubric_assessment_213877_7.json")
    assert seen == [ShowInfo(state.message)]


def test_every_assignment_skipped_fetches_and_writes_nothing(qapp, tmp_path):
    canvas = RubricCanvasClient(assignments=[NO_RUBRIC])
    vm = make_vm(qapp, canvas, tmp_path)
    vm.load_assignments(COURSE_ID)
    vm.set_assignment_ids("12")
    seen = events(vm)
    vm.download_rubric_assessment()
    assert canvas.rubric_calls == []
    state = vm.get_state()
    assert state.status is Status.WARNING
    assert state.message == (
        "Skipped: 'Quiz 3' has no rubric attached. "
        "No rubric-level data will be produced for these assignments."
    )
    assert state.last_saved_path is None
    assert seen == [ShowInfo(state.message)]


def test_typed_id_that_was_never_loaded_is_still_attempted(qapp, tmp_path):
    canvas = RubricCanvasClient(assignments=[NO_RUBRIC])
    vm = make_vm(qapp, canvas, tmp_path)
    vm.set_assignment_ids("12")  # never loaded, so has_rubric is unknown here
    vm.download_rubric_assessment()
    assert canvas.rubric_calls == [12]
    assert vm.get_state().status is Status.NOMINAL
