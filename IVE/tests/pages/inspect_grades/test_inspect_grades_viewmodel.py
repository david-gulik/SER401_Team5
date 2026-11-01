from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from GAVEL.app.workspace.layout import Workspace
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel

TEST_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "workspace"
[COURSE] = Workspace(TEST_WORKSPACE).list_courses()


def test_starts_with_nothing_selected():
    vm = InspectGradesViewModel(dataset_readers=None)

    assert vm.selected_course is None
    assert vm.selected_assignment is None
    assert vm.assignments == ()


def test_select_course_loads_assignments():
    vm = InspectGradesViewModel(dataset_readers=None)

    vm.select_course(COURSE)

    assert vm.selected_course == COURSE
    assert len(vm.assignments) == 2
    assert vm.assignments[0].name == "Module 3: Programming (Gradescope)"
    assert vm.assignments[1].name == "Module 4: ADJ Problem Set"
    assert vm.assignment_error is None


def test_select_assignment():
    vm = InspectGradesViewModel(dataset_readers=None)
    vm.select_course(COURSE)

    assignment = vm.assignments[0]
    vm.select_assignment(assignment)

    assert vm.selected_assignment == assignment


def test_changing_course_clears_selected_assignment():
    vm = InspectGradesViewModel(dataset_readers=None)
    vm.select_course(COURSE)
    vm.select_assignment(vm.assignments[0])

    assert vm.selected_assignment is not None

    vm.select_course(None)

    assert vm.selected_course is None
    assert vm.selected_assignment is None
    assert vm.assignments == ()


def test_missing_manifest():
    vm = InspectGradesViewModel(dataset_readers=None)

    with patch(
        "GAVEL.pages.inspect_grades.viewmodel.CourseDataset.assignments",
        side_effect=OSError("Missing manifest"),
    ):
        vm.select_course(COURSE)

    assert vm.assignments == ()
    assert vm.assignment_error == "Missing manifest"
    assert vm.selected_assignment is None


def test_rejects_invalid_assignment():
    vm = InspectGradesViewModel(dataset_readers=None)
    vm.select_course(COURSE)

    invalid_assignment = replace(vm.assignments[0], canvas_id=-999)

    with pytest.raises(ValueError):
        vm.select_assignment(invalid_assignment)
