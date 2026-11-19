"""A workspace with one course, two modules of anonymized submissions, and two autograders."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from GAVEL.app.workspace.layout import Workspace

COURSE = "ser334_25fc_82931"

GRADER_MAIN = """\
import json
from pathlib import Path

Path("results").mkdir(exist_ok=True)
Path("results/results.json").write_text(json.dumps({"tests": [{"name": "Adds", "score": 2, "max_score": 2}]}))
"""


def _write_grader(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "config.json").write_text(
        json.dumps({"project_location": "/autograder/source/", "files_required": ["answer.txt"]}),
        encoding="utf-8",
    )
    (folder / "main.py").write_text(GRADER_MAIN, encoding="utf-8")


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    submissions = root / "courses" / COURSE / "anonymized" / "gradescope_submissions"
    for module, names in (("m9", ("anon_1093", "anon_4821", "anon_7742")), ("m3", ("anon_2210",))):
        for name in names:
            folder = submissions / module / name
            folder.mkdir(parents=True)
            (folder / "answer.txt").write_text("42", encoding="utf-8")
    # A module with nothing extracted yet is not offered.
    (submissions / "m2").mkdir()

    autograders = root / "autograders" / "ser334"
    _write_grader(autograders / "m9" / "folder_grader")
    staging = tmp_path / "zip_source" / "grader"
    _write_grader(staging)
    with zipfile.ZipFile(autograders / "zipped_grader.zip", "w") as archive:
        for path in staging.rglob("*"):
            if path.is_file():
                archive.write(path, f"grader/{path.relative_to(staging).as_posix()}")
    return root


@pytest.fixture
def workspace(workspace_root: Path) -> Workspace:
    return Workspace(workspace_root)


@pytest.fixture
def course(workspace: Workspace):
    [course] = workspace.list_courses()
    return course
