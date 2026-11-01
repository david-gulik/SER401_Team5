from pathlib import Path

import pytest

from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel

TEST_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "workspace"


@pytest.fixture
def vm():
    return InspectGradesViewModel(
        workspace_root=TEST_WORKSPACE,
        dataset_readers=build_dataset_readers(),
    )


def test_load_courses(vm):
    vm.load_courses()

    assert len(vm.courses) == 1
    assert vm.courses[0].key.folder_name == "ser222_25sc_12345"
    assert vm.selected_course is None
    assert vm.selected_assignment is None


def test_select_course_loads_assignments(vm):
    vm.load_courses()

    vm.select_course(vm.courses[0])

    assert vm.selected_course == vm.courses[0]
    assert len(vm.assignments) == 2
    assert vm.assignments[0].name == "Module 3: Programming (Gradescope)"
    assert vm.assignments[1].name == "Module 4: ADJ Problem Set"
    assert vm.assignment_error is None


def test_select_assignment(vm):
    vm.load_courses()

    vm.select_course(vm.courses[0])

    assignment = vm.assignments[0]
    vm.select_assignment(assignment)

    assert vm.selected_assignment == assignment


def test_changing_course_clears_selected_assignment(vm):
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
        dataset_readers=build_dataset_readers(),
    )

    vm.load_courses()

    assert vm.courses == ()
    assert vm.selected_course is None
    assert vm.assignments == ()


def test_missing_manifest(vm):
    from unittest.mock import patch

    vm.load_courses()

    with patch(
        "GAVEL.pages.inspect_grades.viewmodel.CourseDataset.assignments",
        side_effect=OSError("Missing manifest"),
    ):
        vm.select_course(vm.courses[0])

    assert vm.assignments == ()
    assert vm.assignment_error == "Missing manifest"
    assert vm.selected_assignment is None


def test_rejects_invalid_assignment(vm):
    vm.load_courses()

    vm.select_course(vm.courses[0])

    from dataclasses import replace

    invalid_assignment = replace(vm.assignments[0], canvas_id=-999)

    with pytest.raises(ValueError):
        vm.select_assignment(invalid_assignment)


def test_loads_human_and_proxy_grades(vm):
    vm.load_courses()
    vm.select_course(vm.courses[0])

    assignment = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(assignment)

    assert vm.selected_assignment == assignment
    assert len(vm.human_grades) == 2
    assert len(vm.proxy_grades) == 2
    assert vm.human_grades_error is None
    assert vm.proxy_grades_error is None


def test_switching_assignments_clears_grades(vm):
    vm.load_courses()
    vm.select_course(vm.courses[0])

    module_4 = next(a for a in vm.assignments if a.module_number == 4)
    module_3 = next(a for a in vm.assignments if a.module_number == 3)

    vm.select_assignment(module_4)

    assert len(vm.human_grades) == 2
    assert len(vm.proxy_grades) == 2

    vm.select_assignment(module_3)

    assert vm.selected_assignment == module_3
    assert vm.human_grades == ()
    assert vm.proxy_grades == ()
    assert vm.human_grades_error == "This assignment has no rubric."
    assert vm.proxy_grades_error is not None


def test_clearing_assignment_resets_grades(vm):
    vm.load_courses()
    vm.select_course(vm.courses[0])

    module_4 = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(module_4)
    vm.select_assignment(None)

    assert vm.selected_assignment is None
    assert vm.human_grades == ()
    assert vm.proxy_grades == ()
    assert vm.human_grades_error is None
    assert vm.proxy_grades_error is None


def test_missing_proxy_grades_does_not_block_human_grades(vm, monkeypatch):
    vm.load_courses()
    vm.select_course(vm.courses[0])

    module_4 = next(a for a in vm.assignments if a.module_number == 4)

    def missing_submissions(self, module_number):
        raise FileNotFoundError("Proxy submissions missing")

    monkeypatch.setattr(
        "GAVEL.app.workspace.dataset.CourseDataset.gradescope_submissions",
        missing_submissions,
    )

    vm.select_assignment(module_4)

    assert len(vm.human_grades) == 2
    assert vm.human_grades_error is None
    assert vm.proxy_grades == ()
    assert vm.proxy_grades_error == "Proxy submissions missing"

def test_missing_human_grades_does_not_block_proxy_grades(vm, monkeypatch):
    vm.load_courses()
    vm.select_course(vm.courses[0])

    module_4 = next(
        a for a in vm.assignments if a.module_number == 4
    )

    def missing_assessments(self, assignment_id):
        raise FileNotFoundError("Human assessments missing")

    monkeypatch.setattr(
        "GAVEL.app.workspace.dataset.CourseDataset.rubric_assessments",
        missing_assessments,
    )

    vm.select_assignment(module_4)

    assert vm.human_grades == ()
    assert vm.human_grades_error == "Human assessments missing"
    assert len(vm.proxy_grades) == 2
    assert vm.proxy_grades_error is None
