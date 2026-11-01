from __future__ import annotations

import json
from pathlib import Path

import pytest

from GAVEL.app.usecases.proxy_grade.mappings.ser334_m9 import SER334_M9
from GAVEL.app.workspace.dataset import DatasetReaders
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import (
    AssignmentEntry,
    new_manifest,
    record_assignment,
    save_manifest,
)
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.analytics.generate_report_viewmodel import GenerateReportViewModel

_FOLDER_NAME = "ser222_25sc_12345"
_MODULE_9_COLUMN = "Module 9: Programming (Gradescope) (9001)"
_OTHER_COLUMN = "Module 1: Activity (5001)"
_ALL_TEST_NAMES = list(SER334_M9.test_names())
_RUBRIC_ASSIGNMENT_ID = 9002


@pytest.fixture
def readers() -> DatasetReaders:
    return build_dataset_readers()


def _write_gradebook(path: Path, student_a_score: str, student_b_score: str) -> None:
    path.write_text(
        "Student,ID,SIS Login ID,Section,"
        f"{_OTHER_COLUMN},{_MODULE_9_COLUMN},Current Points\n"
        ",,,,Manual Posting,,\n"
        "    Points Possible,,,,10.00,32.00,(read only)\n"
        f'"A, Student",1001,student_a,001,5.00,{student_a_score},100.00\n'
        f'"B, Student",1002,student_b,001,0.00,{student_b_score},80.00\n',
        encoding="utf-8",
    )


def _submission_block(sid: str, email: str, name: str, passing: set[str]) -> str:
    tests = "".join(
        f'      - name: "{test_name}"\n        score: {1.0 if test_name in passing else 0.0}\n'
        "        max_score: 1.0\n"
        for test_name in _ALL_TEST_NAMES
    )
    return (
        f"submission_{sid}:\n"
        "  :created_at: 2026-01-01 00:00:00\n"
        "  :submitters:\n"
        f"  - :sid: '{sid}'\n"
        f"    :email: {email}\n"
        f"    :name: {name}\n"
        "  :results:\n"
        "    tests:\n" + tests
    )


def _write_submissions(path: Path, passing_a: set[str], passing_b: set[str]) -> None:
    path.write_text(
        _submission_block("1001", "student_a@asu.edu", "A Student", passing_a)
        + _submission_block("1002", "student_b@asu.edu", "B Student", passing_b),
        encoding="utf-8",
    )


def _write_rubric_definition(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "rubric_id": "1",
                "title": "M9 rubric",
                "points_possible": sum(c.tiers[0].points for c in SER334_M9.criteria),
                "free_form_criterion_comments": False,
                "criteria": [
                    {
                        "id": f"c{i}",
                        "description": criterion.name,
                        "points": criterion.tiers[0].points,
                        "ratings": [],
                    }
                    for i, criterion in enumerate(SER334_M9.criteria)
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_rubric_assessments(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "student_id": student_id,
                    "submission_id": student_id,
                    "criteria": [
                        {
                            "criterion_id": f"c{i}",
                            "points": criterion.tiers[0].points if full_marks else 0.0,
                            "comments": "",
                        }
                        for i, criterion in enumerate(SER334_M9.criteria)
                    ],
                }
                for student_id, full_marks in ((1001, True), (1002, False))
            ]
        ),
        encoding="utf-8",
    )


def _build_course(
    tmp_path: Path, *, with_manifest: bool = False, with_rubric: bool = False
) -> Path:
    folder = Workspace(tmp_path).course(CourseKey.parse(_FOLDER_NAME))
    folder.anonymized.root.mkdir(parents=True)

    _write_gradebook(folder.anonymized.gradebook_csv, "32.0", "10.0")

    module = folder.anonymized.module_submissions(9)
    module.extracted_dir.mkdir(parents=True)
    _write_submissions(
        module.extracted_dir / "submission_metadata.yml",
        passing_a=set(_ALL_TEST_NAMES),
        passing_b=set(),
    )

    if with_rubric:
        assignment_folder = folder.anonymized.assignment(_RUBRIC_ASSIGNMENT_ID, module_number=9)
        _write_rubric_definition(assignment_folder.rubric_definition_json)
        _write_rubric_assessments(assignment_folder.rubric_assessments_json)

    if with_manifest or with_rubric:
        manifest = new_manifest(folder.key)
        manifest = record_assignment(
            manifest,
            AssignmentEntry(
                canvas_id=9001, name="Programming (Gradescope)", module_number=9, has_rubric=False
            ),
        )
        manifest = record_assignment(
            manifest,
            AssignmentEntry(canvas_id=5001, name="Activity", module_number=1, has_rubric=False),
        )
        if with_rubric:
            manifest = record_assignment(
                manifest,
                AssignmentEntry(
                    canvas_id=_RUBRIC_ASSIGNMENT_ID,
                    name="Programming (Manual)",
                    module_number=9,
                    has_rubric=True,
                ),
            )
        save_manifest(folder.manifest_path, manifest)

    return tmp_path


def _course(workspace_root: Path, readers: DatasetReaders) -> CourseFolder:
    return GenerateReportViewModel(readers).list_courses(workspace_root)[0]


def test_lists_courses_found_in_the_workspace(tmp_path: Path, readers: DatasetReaders) -> None:
    workspace_root = _build_course(tmp_path)

    courses = GenerateReportViewModel(readers).list_courses(workspace_root)

    assert [c.key.folder_name for c in courses] == [_FOLDER_NAME]


def test_lists_only_modules_with_submissions(tmp_path: Path, readers: DatasetReaders) -> None:
    workspace_root = _build_course(tmp_path)
    vm = GenerateReportViewModel(readers)
    course = _course(workspace_root, readers)

    assert vm.list_modules(course) == (9,)


def test_resolve_mapping_name_finds_the_course_and_module_s_own_mapping() -> None:
    vm = GenerateReportViewModel(build_dataset_readers())
    course = CourseFolder(path=Path("unused"), key=CourseKey.parse("ser334_25sc_12345"))

    assert vm.resolve_mapping_name(course, 2) == "ser334_m2"


def test_resolve_mapping_name_with_no_matching_mapping_gives_none() -> None:
    vm = GenerateReportViewModel(build_dataset_readers())
    course = CourseFolder(path=Path("unused"), key=CourseKey.parse("ser334_25sc_12345"))

    assert vm.resolve_mapping_name(course, 404) is None


def test_generate_writes_a_report_to_the_runs_folder(
    tmp_path: Path, readers: DatasetReaders
) -> None:
    workspace_root = _build_course(tmp_path)
    vm = GenerateReportViewModel(readers)
    course = _course(workspace_root, readers)

    outcome = vm.generate(workspace_root, course, 9, "ser334_m9", _MODULE_9_COLUMN)

    assert outcome.scored == 2
    assert outcome.unmatched == 0
    assert outcome.failed == 0
    assert outcome.output_path.exists()
    assert outcome.output_path.parent == Workspace(workspace_root).runs_dir


def test_gradebook_columns_narrows_to_the_selected_module(
    tmp_path: Path, readers: DatasetReaders
) -> None:
    workspace_root = _build_course(tmp_path, with_manifest=True)
    vm = GenerateReportViewModel(readers)
    course = _course(workspace_root, readers)

    columns = vm.list_gradebook_columns(course, 9)

    assert columns == (_MODULE_9_COLUMN,)


def test_gradebook_columns_without_a_manifest_still_lists_every_column(
    tmp_path: Path, readers: DatasetReaders
) -> None:
    workspace_root = _build_course(tmp_path, with_manifest=False)
    vm = GenerateReportViewModel(readers)
    course = _course(workspace_root, readers)

    columns = vm.list_gradebook_columns(course, 9)

    assert set(columns) == {_MODULE_9_COLUMN, _OTHER_COLUMN}


def test_rubric_assignments_lists_only_assignments_with_a_rubric(
    tmp_path: Path, readers: DatasetReaders
) -> None:
    workspace_root = _build_course(tmp_path, with_rubric=True)
    vm = GenerateReportViewModel(readers)
    course = _course(workspace_root, readers)

    assignments = vm.list_rubric_assignments(course, 9)

    assert [a.canvas_id for a in assignments] == [_RUBRIC_ASSIGNMENT_ID]


def test_rubric_assignments_without_a_manifest_lists_none(
    tmp_path: Path, readers: DatasetReaders
) -> None:
    workspace_root = _build_course(tmp_path)
    vm = GenerateReportViewModel(readers)
    course = _course(workspace_root, readers)

    assert vm.list_rubric_assignments(course, 9) == ()


def test_generate_heat_map_writes_a_report_to_the_runs_folder(
    tmp_path: Path, readers: DatasetReaders
) -> None:
    workspace_root = _build_course(tmp_path, with_rubric=True)
    vm = GenerateReportViewModel(readers)
    course = _course(workspace_root, readers)
    rubric_assignment = vm.list_rubric_assignments(course, 9)[0]

    outcome = vm.generate_heat_map(workspace_root, course, 9, "ser334_m9", rubric_assignment)

    assert outcome.scored == len(SER334_M9.criteria) * 2
    assert outcome.unmatched == 0
    assert outcome.failed == 0
    assert outcome.missing_human_scores == 0
    assert outcome.output_path.exists()
    assert outcome.output_path.parent == Workspace(workspace_root).runs_dir
    assert (
        outcome.output_path
        != vm.generate(workspace_root, course, 9, "ser334_m9", _MODULE_9_COLUMN).output_path
    )
