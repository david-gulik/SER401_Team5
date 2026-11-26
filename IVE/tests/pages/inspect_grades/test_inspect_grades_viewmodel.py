from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from GAVEL.app.usecases.proxy_grade.mappings.ser334_m2 import SER334_M2
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import AssignmentEntry
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.inspect_grades.correction_store import (
    load_corrections,
    save_corrections,
)
from GAVEL.pages.inspect_grades.viewmodel import InspectGradesViewModel

TEST_WORKSPACE = Path(__file__).resolve().parents[2] / "data" / "workspace"
[COURSE] = Workspace(TEST_WORKSPACE).list_courses()


@pytest.fixture
def vm():
    return InspectGradesViewModel(dataset_readers=build_dataset_readers())


@pytest.fixture(autouse=True)
def isolate_correction_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        InspectGradesViewModel,
        "_corrections_path",
        lambda self: (
            tmp_path / f"{self.selected_assignment.canvas_id}.json"
            if self.selected_assignment is not None
            else None
        ),
    )


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


def test_stores_rubric_corrections():
    vm = InspectGradesViewModel(dataset_readers=build_dataset_readers())

    vm.set_correction(100002, "crit_2", 2.0)

    assert vm.get_correction(100002, "crit_2") == 2.0
    assert vm.get_correction(100001, "crit_2") is None
    assert vm.get_correction(100002, "crit_1") is None


def test_overwrites_existing_rubric_correction():
    vm = InspectGradesViewModel(dataset_readers=build_dataset_readers())

    vm.set_correction(100002, "crit_2", 2.0)
    vm.set_correction(100002, "crit_2", 0.0)

    assert vm.get_correction(100002, "crit_2") == 0.0
    assert len(vm.corrections) == 1


def test_selecting_assignment_loads_saved_corrections(tmp_path, monkeypatch):
    vm = InspectGradesViewModel(dataset_readers=build_dataset_readers())
    vm.select_course(COURSE)

    correction_file = tmp_path / "corrections" / "7216983.json"

    save_corrections(
        correction_file,
        {(100002, "crit_2"): 2.0},
        {(100002, "crit_2"): "Awarded full credit."},
    )

    monkeypatch.setattr(
        vm,
        "_corrections_path",
        lambda: correction_file,
    )

    vm.select_assignment(vm.assignments[1])

    assert vm.get_correction(100002, "crit_2") == 2.0
    assert vm.notes[(100002, "crit_2")] == "Awarded full credit."

    vm.select_assignment(None)

    assert vm.corrections == {}
    assert vm.notes == {}

    vm.select_assignment(vm.assignments[1])

    assert vm.get_correction(100002, "crit_2") == 2.0
    assert vm.notes[(100002, "crit_2")] == "Awarded full credit."


def test_saves_current_assignment_corrections(tmp_path, monkeypatch):
    vm = InspectGradesViewModel(dataset_readers=build_dataset_readers())
    vm.select_course(COURSE)

    correction_file = tmp_path / "corrections" / "7216983.json"

    monkeypatch.setattr(
        vm,
        "_corrections_path",
        lambda: correction_file,
    )

    assignment = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(assignment)

    vm.set_correction(100002, "crit_2", 2.0)
    vm.notes[(100002, "crit_2")] = "Awarded full credit."

    vm.save_current_corrections()

    assert correction_file.is_file()

    saved_scores, saved_notes = load_corrections(correction_file)

    assert saved_scores == {(100002, "crit_2"): 2.0}
    assert saved_notes == {(100002, "crit_2"): "Awarded full credit."}

    restored_vm = InspectGradesViewModel(dataset_readers=build_dataset_readers())
    restored_vm.select_course(COURSE)

    monkeypatch.setattr(
        restored_vm,
        "_corrections_path",
        lambda: correction_file,
    )

    restored_vm.select_assignment(restored_vm.assignments[1])

    assert restored_vm.get_correction(100002, "crit_2") == 2.0
    assert restored_vm.notes[(100002, "crit_2")] == "Awarded full credit."


def test_corrupted_correction_file_does_not_block_grades(vm, tmp_path, monkeypatch):
    vm.select_course(COURSE)

    correction_file = tmp_path / "corrections.json"
    correction_file.write_text(
        "{invalid json",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        vm,
        "_corrections_path",
        lambda: correction_file,
    )

    assignment = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(assignment)

    assert vm.corrections == {}
    assert vm.notes == {}
    assert vm.corrections_error is not None
    assert "Could not load saved corrections" in vm.corrections_error

    assert len(vm.human_grades) == 2
    assert len(vm.proxy_grades) == 2
    assert vm.rubric_definition is not None

    assert correction_file.read_text(encoding="utf-8") == "{invalid json"


def test_corrupted_correction_file_cannot_be_overwritten(vm, tmp_path, monkeypatch):
    vm.select_course(COURSE)

    correction_file = tmp_path / "corrections.json"
    correction_file.write_text(
        "{invalid json",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        vm,
        "_corrections_path",
        lambda: correction_file,
    )

    assignment = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(assignment)

    assert vm.corrections_error is not None

    vm.set_correction(100002, "crit_2", 2.0)
    vm.notes[(100002, "crit_2")] = "Updated grade."

    vm.save_current_corrections()

    assert correction_file.read_text(encoding="utf-8") == "{invalid json"


@pytest.mark.parametrize(
    "student_id, criterion_id, score",
    [
        (999999, "crit_2", 2.0),
        (100002, "invalid_criterion", 2.0),
        (100002, "crit_2", 10.0),
    ],
)
def test_rejects_corrections_not_matching_assignment(
    vm, tmp_path, monkeypatch, student_id, criterion_id, score
):
    vm.select_course(COURSE)

    correction_file = tmp_path / "corrections.json"

    save_corrections(
        correction_file,
        {(student_id, criterion_id): score},
        {},
    )

    original_content = correction_file.read_text(encoding="utf-8")

    monkeypatch.setattr(
        vm,
        "_corrections_path",
        lambda: correction_file,
    )

    assignment = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(assignment)

    assert vm.corrections == {}
    assert vm.notes == {}
    assert vm.corrections_error is not None
    assert "Could not load saved corrections" in vm.corrections_error

    assert len(vm.human_grades) == 2
    assert vm.rubric_definition is not None

    vm.save_current_corrections()

    assert correction_file.read_text(encoding="utf-8") == original_content


@pytest.mark.parametrize(
    "missing_data",
    ["rubric", "human_grades"],
)
def test_saved_corrections_require_grading_data(vm, tmp_path, monkeypatch, missing_data):
    vm.select_course(COURSE)

    correction_file = tmp_path / "corrections.json"

    save_corrections(
        correction_file,
        {(100002, "crit_2"): 2.0},
        {},
    )

    original_content = correction_file.read_text(encoding="utf-8")

    monkeypatch.setattr(
        vm,
        "_corrections_path",
        lambda: correction_file,
    )

    if missing_data == "rubric":
        monkeypatch.setattr(
            "GAVEL.pages.inspect_grades.viewmodel.CourseDataset.rubric_definition",
            lambda self, assignment_id: None,
        )
    else:
        monkeypatch.setattr(
            "GAVEL.pages.inspect_grades.viewmodel.CourseDataset.rubric_assessments",
            lambda self, assignment_id: (),
        )

    assignment = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(assignment)

    assert vm.corrections == {}
    assert vm.notes == {}
    assert vm.corrections_error is not None
    assert "Could not validate saved corrections" in vm.corrections_error

    vm.save_current_corrections()

    assert correction_file.read_text(encoding="utf-8") == original_content


def test_save_corrections_handles_file_error(vm, tmp_path, monkeypatch):
    vm.select_course(COURSE)

    correction_file = tmp_path / "corrections.json"

    monkeypatch.setattr(
        vm,
        "_corrections_path",
        lambda: correction_file,
    )

    assignment = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(assignment)

    vm.set_correction(100002, "crit_2", 2.0)

    def fail_save(path, corrections, notes):
        raise PermissionError("Access denied")

    monkeypatch.setattr(
        "GAVEL.pages.inspect_grades.viewmodel.save_corrections",
        fail_save,
    )

    vm.save_current_corrections()

    assert vm.corrections_error is not None
    assert "Could not save rubric corrections" in vm.corrections_error
    assert "Access denied" in vm.corrections_error

    assert not correction_file.exists()


def test_resolve_mapping_name_for_supported_course(vm):
    course = CourseFolder(
        path=Path("unused"),
        key=CourseKey.parse("ser334_25sc_12345"),
    )

    vm.selected_course = course
    vm.selected_assignment = AssignmentEntry(
        canvas_id=12345,
        name="Module 2",
        module_number=2,
        has_rubric=True,
    )

    assert vm.resolve_mapping_name() == "ser334_m2"


def test_resolve_mapping_name_for_unsupported_course(vm):
    vm.select_course(COURSE)
    vm.select_assignment(vm.assignments[1])

    assert vm.resolve_mapping_name() is None


def test_loads_gradebook_for_selected_assignment(vm, monkeypatch):
    vm.select_course(COURSE)

    expected_gradebook = object()

    monkeypatch.setattr(
        "GAVEL.pages.inspect_grades.viewmodel.CourseDataset.gradebook",
        lambda self: expected_gradebook,
    )

    assignment = next(a for a in vm.assignments if a.module_number == 4)

    vm.select_assignment(assignment)

    assert vm.gradebook is expected_gradebook
    assert vm.gradebook_error is None

    vm.select_assignment(None)

    assert vm.gradebook is None
    assert vm.gradebook_error is None


def test_matches_gradescope_submissions_to_canvas_students(vm):
    vm.gradebook = SimpleNamespace(
        rows=[
            SimpleNamespace(sis_login_id="student1", canvas_id=100001),
            SimpleNamespace(sis_login_id="student2", canvas_id=100002),
        ]
    )

    submission_1 = SimpleNamespace(submitter=SimpleNamespace(email="student1@example.com"))
    submission_2 = SimpleNamespace(submitter=SimpleNamespace(email="STUDENT2@example.com"))
    unmatched = SimpleNamespace(submitter=SimpleNamespace(email="unknown@example.com"))

    vm.proxy_grades = (submission_1, submission_2, unmatched)

    matched = vm.matched_proxy_submissions()

    assert matched == {
        100001: submission_1,
        100002: submission_2,
    }


def test_duplicate_gradescope_submissions_are_not_matched(vm):
    vm.gradebook = SimpleNamespace(
        rows=[
            SimpleNamespace(sis_login_id="student1", canvas_id=100001),
            SimpleNamespace(sis_login_id="student2", canvas_id=100002),
        ]
    )

    first = SimpleNamespace(submitter=SimpleNamespace(email="student1@example.com"))
    duplicate = SimpleNamespace(submitter=SimpleNamespace(email="STUDENT1@example.com"))
    valid = SimpleNamespace(submitter=SimpleNamespace(email="student2@example.com"))

    vm.proxy_grades = (first, duplicate, valid)

    assert vm.matched_proxy_submissions() == {
        100002: valid,
    }


def test_calculates_proxy_scores_for_matched_students(vm, monkeypatch):
    mapping = SimpleNamespace(
        criteria=[
            SimpleNamespace(name="Problem 1"),
            SimpleNamespace(name="Problem 2"),
        ],
    )

    rubric = SimpleNamespace(
        criteria=[
            SimpleNamespace(id="crit_1"),
            SimpleNamespace(id="crit_2"),
        ],
    )

    submission = object()

    vm.rubric_definition = rubric

    monkeypatch.setattr(
        vm,
        "resolve_mapping_name",
        lambda: "test_mapping",
    )
    monkeypatch.setitem(
        __import__(
            "GAVEL.pages.inspect_grades.viewmodel",
            fromlist=["MAPPINGS"],
        ).MAPPINGS,
        "test_mapping",
        mapping,
    )
    monkeypatch.setattr(
        vm,
        "matched_proxy_submissions",
        lambda: {100002: submission},
    )
    monkeypatch.setattr(
        "GAVEL.pages.inspect_grades.viewmodel.match_proxy_criteria_to_rubric",
        lambda mapping, rubric: {
            "Problem 1": rubric.criteria[0],
            "Problem 2": rubric.criteria[1],
        },
    )
    monkeypatch.setattr(
        "GAVEL.pages.inspect_grades.viewmodel.compute_proxy_grade",
        lambda submission, mapping: SimpleNamespace(
            criterion_scores=(3.0, 2.0),
            total_score=5.0,
        ),
    )

    assert vm.calculated_proxy_scores() == {
        100002: {
            "crit_1": 3.0,
            "crit_2": 2.0,
        }
    }


def test_proxy_calculation_handles_unmatched_rubric(vm, monkeypatch):
    mapping = SimpleNamespace(criteria=[SimpleNamespace(name="Unknown Problem")])
    vm.rubric_definition = SimpleNamespace(criteria=[])

    monkeypatch.setattr(
        vm,
        "resolve_mapping_name",
        lambda: "test_mapping",
    )

    monkeypatch.setitem(
        __import__(
            "GAVEL.pages.inspect_grades.viewmodel",
            fromlist=["MAPPINGS"],
        ).MAPPINGS,
        "test_mapping",
        mapping,
    )

    def fail_matching(mapping, rubric):
        raise ValueError("No rubric criterion matches: Unknown Problem")

    monkeypatch.setattr(
        "GAVEL.pages.inspect_grades.viewmodel.match_proxy_criteria_to_rubric",
        fail_matching,
    )

    assert vm.calculated_proxy_scores() == {}
    assert vm.proxy_calculation_error is not None
    assert "Unknown Problem" in vm.proxy_calculation_error


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


def test_calculates_proxy_scores_using_real_mapping(vm, monkeypatch):
    mapping = SER334_M2

    vm.rubric_definition = SimpleNamespace(
        criteria=[
            SimpleNamespace(
                id=f"crit_{index}",
                description=criterion.name,
            )
            for index, criterion in enumerate(mapping.criteria, start=1)
        ]
    )

    vm.gradebook = SimpleNamespace(
        rows=[
            SimpleNamespace(
                sis_login_id="student1",
                canvas_id=100001,
            )
        ]
    )

    passing_tests = {
        "Main Menu 1",
        "Memory Allocation 2",
        "Memory Allocation 3",
    }

    tests = tuple(
        SimpleNamespace(
            name=name,
            score=1.0 if name in passing_tests else 0.0,
            max_score=1.0,
        )
        for name in mapping.test_names()
    )

    submission = SimpleNamespace(
        submitter=SimpleNamespace(
            email="student1@example.com",
        ),
        tests=tests,
    )

    vm.proxy_grades = (submission,)

    monkeypatch.setattr(
        vm,
        "resolve_mapping_name",
        lambda: "ser334_m2",
    )

    scores = vm.calculated_proxy_scores()

    assert scores == {
        100001: {
            "crit_1": 1.0,
            "crit_2": 2.0,
            "crit_3": 0.0,
            "crit_4": 0.0,
            "crit_5": 0.0,
            "crit_6": 0.0,
            "crit_7": 0.0,
            "crit_8": 0.0,
            "crit_9": 0.0,
        }
    }

    assert sum(scores[100001].values()) == 3.0
    assert vm.proxy_calculation_error is None


@pytest.mark.parametrize(
    "tests, output, expected_zero",
    [
        (
            (SimpleNamespace(name="Main Menu 1", score=1.0, max_score=1.0),),
            "",
            False,
        ),
        (
            (),
            "The submitted code could not be compiled.",
            True,
        ),
        (
            (),
            "The autograder failed to execute correctly.",
            False,
        ),
    ],
    ids=[
        "missing_required_tests",
        "no_tests_ran_on_submitted_code",
        "autograder_crashed",
    ],
)
def test_proxy_scores_handle_incomplete_test_results(vm, monkeypatch, tests, output, expected_zero):
    mapping = SER334_M2

    vm.rubric_definition = SimpleNamespace(
        criteria=[
            SimpleNamespace(
                id=f"crit_{index}",
                description=criterion.name,
            )
            for index, criterion in enumerate(mapping.criteria, start=1)
        ]
    )

    vm.gradebook = SimpleNamespace(
        rows=[
            SimpleNamespace(
                sis_login_id="student1",
                canvas_id=100001,
            )
        ]
    )

    vm.proxy_grades = (
        SimpleNamespace(
            submitter=SimpleNamespace(
                email="student1@example.com",
            ),
            tests=tests,
            output=output,
        ),
    )

    monkeypatch.setattr(
        vm,
        "resolve_mapping_name",
        lambda: "ser334_m2",
    )

    scores = vm.calculated_proxy_scores()

    if expected_zero:
        assert scores == {
            100001: {f"crit_{index}": 0.0 for index in range(1, len(mapping.criteria) + 1)}
        }
    else:
        assert scores == {}

    assert vm.proxy_calculation_error is None
