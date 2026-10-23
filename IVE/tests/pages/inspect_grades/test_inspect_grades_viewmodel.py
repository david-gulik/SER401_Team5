from pathlib import Path

import pytest

from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel

TEST_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "workspace"


def test_load_courses():
    vm = InspectGradesViewModel(
        workspace_root=TEST_WORKSPACE,
        dataset_readers=None,
    )

    vm.load_courses()

    assert len(vm.courses) == 1
    assert vm.courses[0].key.folder_name == "ser222_25sc_12345"
    assert vm.selected_course is None
    assert vm.selected_assignment is None


def test_select_course_loads_assignments():
    vm = InspectGradesViewModel(
        workspace_root=TEST_WORKSPACE,
        dataset_readers=None,
    )

    vm.load_courses()
    vm.select_course(vm.courses[0])

    assert vm.selected_course == vm.courses[0]
    assert len(vm.assignments) == 2
    assert vm.assignments[0].name == "Module 3: Programming (Gradescope)"
    assert vm.assignments[1].name == "Module 4: ADJ Problem Set"
    assert vm.assignment_error is None


def test_select_assignment():
    vm = InspectGradesViewModel(
        workspace_root=TEST_WORKSPACE,
        dataset_readers=None,
    )

    vm.load_courses()
    vm.select_course(vm.courses[0])

    assignment = vm.assignments[0]
    vm.select_assignment(assignment)

    assert vm.selected_assignment == assignment


def test_changing_course_clears_selected_assignment():
    vm = InspectGradesViewModel(
        workspace_root=TEST_WORKSPACE,
        dataset_readers=None,
    )

    vm.load_courses()
    vm.select_course(vm.courses[0])
    vm.select_assignment(vm.assignments[0])

    assert vm.selected_assignment is not None

    vm.select_course(None)

    assert vm.selected_course is None
    assert vm.selected_assignment is None
    assert vm.assignments == ()


def test_empty_workspace(tmp_path):
    vm = InspectGradesViewModel(
        workspace_root=tmp_path,
        dataset_readers=None,
    )

    vm.load_courses()

    assert vm.courses == ()
    assert vm.selected_course is None
    assert vm.assignments == ()


def test_missing_manifest():
    from unittest.mock import patch

    vm = InspectGradesViewModel(
        workspace_root=TEST_WORKSPACE,
        dataset_readers=None,
    )

    vm.load_courses()

    with patch(
        "GAVEL.pages.inspect_grades.viewmodel.CourseDataset.assignments",
        side_effect=OSError("Missing manifest"),
    ):
        vm.select_course(vm.courses[0])

    assert vm.assignments == ()
    assert vm.assignment_error == "Missing manifest"
    assert vm.selected_assignment is None


def test_rejects_invalid_assignment():
    vm = InspectGradesViewModel(
        workspace_root=TEST_WORKSPACE,
        dataset_readers=None,
    )

    vm.load_courses()
    vm.select_course(vm.courses[0])

    from dataclasses import replace

    invalid_assignment = replace(vm.assignments[0], canvas_id=-999)

    with pytest.raises(ValueError):
        vm.select_assignment(invalid_assignment)
