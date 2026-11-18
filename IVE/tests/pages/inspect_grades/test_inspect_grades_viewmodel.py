from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from GAVEL.app.workspace.layout import Workspace
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel

TEST_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "workspace"
[COURSE] = Workspace(TEST_WORKSPACE).list_courses()


@pytest.fixture
def vm():
    return InspectGradesViewModel(dataset_readers=build_dataset_readers())


def test_starts_with_nothing_selected(vm):
    assert vm.selected_course is None
    assert vm.selected_assignment is None
    assert vm.assignments == ()
    assert vm.human_grades == ()
    assert vm.proxy_grades == ()


def test_select_course_loads_assignments(vm):
    vm.select_course(COURSE)

    assert vm.selected_course == COURSE
    assert len(vm.assignments) == 2
    assert vm.assignments[0].name == "Module 3: Programming (Gradescope)"
    assert vm.assignments[1].name == "Module 4: ADJ Problem Set"
    assert vm.assignment_error is None


def test_select_assignment(vm):
    vm.select_course(COURSE)

    assignment = vm.assignments[0]
    vm.select_assignment(assignment)

    assert vm.selected_assignment == assignment


def test_changing_course_clears_selected_assignment(vm):
    vm.select_course(COURSE)
    vm.select_assignment(vm.assignments[0])

    assert vm.selected_assignment is not None

    vm.select_course(None)

    assert vm.selected_course is None
    assert vm.selected_assignment is None
    assert vm.assignments == ()
    assert vm.human_grades == ()
    assert vm.proxy_grades == ()


def test_empty_workspace(tmp_path):
    courses = Workspace(tmp_path).list_courses()

    assert courses == []

    vm = InspectGradesViewModel(dataset_readers=build_dataset_readers())

    assert vm.selected_course is None
    assert vm.selected_assignment is None
    assert vm.assignments == ()


def test_missing_manifest(vm):
    with patch(
        "GAVEL.pages.inspect_grades.viewmodel.CourseDataset.assignments",
        side_effect=OSError("Missing manifest"),
    ):
        vm.select_course(COURSE)

    assert vm.assignments == ()
    assert vm.assignment_error == "Missing manifest"
    assert vm.selected_assignment is None


def test_rejects_invalid_assignment(vm):
    vm.select_course(COURSE)

    invalid_assignment = replace(
        vm.assignments[0],
        canvas_id=-999,
    )

    with pytest.raises(ValueError):
        vm.select_assignment(invalid_assignment)


def test_loads_human_and_proxy_grades(vm):
    vm.select_course(COURSE)

    assignment = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(assignment)

    assert vm.selected_assignment == assignment
    assert len(vm.human_grades) == 2
    assert len(vm.proxy_grades) == 2
    assert vm.human_grades_error is None
    assert vm.proxy_grades_error is None


def test_switching_assignments_clears_grades(vm):
    vm.select_course(COURSE)

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
    vm.select_course(COURSE)

    module_4 = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(module_4)
    vm.select_assignment(None)

    assert vm.selected_assignment is None
    assert vm.human_grades == ()
    assert vm.proxy_grades == ()
    assert vm.human_grades_error is None
    assert vm.proxy_grades_error is None


def test_missing_proxy_grades_does_not_block_human_grades(vm, monkeypatch):
    vm.select_course(COURSE)

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
    vm.select_course(COURSE)

    module_4 = next(a for a in vm.assignments if a.module_number == 4)

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


@pytest.mark.parametrize("error_type", [KeyError, IndexError])
def test_malformed_proxy_data_is_handled(vm, monkeypatch, error_type):
    vm.select_course(COURSE)

    module_4 = next(a for a in vm.assignments if a.module_number == 4)

    def malformed_submissions(self, module_number):
        raise error_type("Malformed grading data")

    monkeypatch.setattr(
        "GAVEL.app.workspace.dataset.CourseDataset.gradescope_submissions",
        malformed_submissions,
    )

    vm.select_assignment(module_4)

    assert len(vm.human_grades) == 2
    assert vm.proxy_grades == ()
    assert vm.proxy_grades_error is not None


@pytest.mark.parametrize("error_type", [KeyError, IndexError])
def test_malformed_human_data_is_handled(vm, monkeypatch, error_type):
    vm.select_course(COURSE)

    module_4 = next(a for a in vm.assignments if a.module_number == 4)

    def malformed_assessments(self, assignment_id):
        raise error_type("Malformed human grading data")

    monkeypatch.setattr(
        "GAVEL.app.workspace.dataset.CourseDataset.rubric_assessments",
        malformed_assessments,
    )

    vm.select_assignment(module_4)

    assert vm.human_grades == ()
    assert vm.human_grades_error is not None
    assert len(vm.proxy_grades) == 2
    assert vm.proxy_grades_error is None


def test_loads_rubric_definition(vm, monkeypatch):
    vm.select_course(COURSE)
    assignment = next(a for a in vm.assignments if a.module_number == 4)

    expected_rubric = object()

    monkeypatch.setattr(
        "GAVEL.app.workspace.dataset.CourseDataset.rubric_definition",
        lambda self, assignment_id: expected_rubric,
    )

    vm.select_assignment(assignment)

    assert vm.rubric_definition is expected_rubric
    assert vm.rubric_definition_error is None
    assert len(vm.human_grades) == 2
    assert len(vm.proxy_grades) == 2


def test_missing_rubric_definition_does_not_block_grades(vm, monkeypatch):
    vm.select_course(COURSE)
    assignment = next(a for a in vm.assignments if a.module_number == 4)

    monkeypatch.setattr(
        "GAVEL.app.workspace.dataset.CourseDataset.rubric_definition",
        lambda self, assignment_id: None,
    )

    vm.select_assignment(assignment)

    assert vm.rubric_definition is None
    assert vm.rubric_definition_error is not None
    assert len(vm.human_grades) == 2
    assert len(vm.proxy_grades) == 2

    vm.select_assignment(None)

    assert vm.rubric_definition is None
    assert vm.rubric_definition_error is None


def test_autograder_zips_are_discovered(vm, tmp_path):
    from GAVEL.app.workspace.layout import CourseFolder, Workspace

    workspace = Workspace(tmp_path)
    course = CourseFolder(
        workspace.courses_dir / COURSE.key.folder_name,
        COURSE.key,
    )

    autograder_dir = workspace.course_autograders_dir(course.key)
    autograder_dir.mkdir(parents=True)

    first_zip = autograder_dir / "autograder_v1.zip"
    second_zip = autograder_dir / "autograder_v2.zip"

    first_zip.touch()
    second_zip.touch()
    (autograder_dir / "notes.txt").touch()

    vm.select_course(course)

    assert vm.available_autograder_zips == (first_zip, second_zip)
    assert vm.selected_autograder_zip is None
    assert vm.autograder_zip_error is None


def test_autograder_selection_resets_when_course_changes(vm, tmp_path):
    from GAVEL.app.workspace.layout import CourseFolder, Workspace

    workspace = Workspace(tmp_path)
    course = CourseFolder(
        workspace.courses_dir / COURSE.key.folder_name,
        COURSE.key,
    )

    autograder_dir = workspace.course_autograders_dir(course.key)
    autograder_dir.mkdir(parents=True)

    zip_path = autograder_dir / "autograder.zip"
    zip_path.touch()

    vm.select_course(course)
    vm.select_autograder_zip(zip_path)

    assert vm.selected_autograder_zip == zip_path

    vm.select_course(None)

    assert vm.available_autograder_zips == ()
    assert vm.selected_autograder_zip is None


def test_rejects_unknown_autograder_zip(vm, tmp_path):
    from GAVEL.app.workspace.layout import CourseFolder, Workspace

    workspace = Workspace(tmp_path)
    course = CourseFolder(
        workspace.courses_dir / COURSE.key.folder_name,
        COURSE.key,
    )

    vm.select_course(course)

    with pytest.raises(ValueError):
        vm.select_autograder_zip(tmp_path / "unknown.zip")
