from __future__ import annotations

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


def _build_course(tmp_path: Path, *, with_manifest: bool = False) -> Path:
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

    if with_manifest:
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


def test_mapping_names_lists_the_registry() -> None:
    names = GenerateReportViewModel(build_dataset_readers()).mapping_names()

    assert "ser334_m9" in names


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


def test_gradebook_columns_lists_the_selected_module_s_column_first(
    tmp_path: Path, readers: DatasetReaders
) -> None:
    workspace_root = _build_course(tmp_path, with_manifest=True)
    vm = GenerateReportViewModel(readers)
    course = _course(workspace_root, readers)

    columns = vm.list_gradebook_columns(course, 9)

    assert columns[0] == _MODULE_9_COLUMN
    assert set(columns) == {_MODULE_9_COLUMN, _OTHER_COLUMN}


def test_gradebook_columns_without_a_manifest_still_lists_every_column(
    tmp_path: Path, readers: DatasetReaders
) -> None:
    workspace_root = _build_course(tmp_path, with_manifest=False)
    vm = GenerateReportViewModel(readers)
    course = _course(workspace_root, readers)

    columns = vm.list_gradebook_columns(course, 9)

    assert set(columns) == {_MODULE_9_COLUMN, _OTHER_COLUMN}
