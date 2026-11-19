from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

from GAVEL.app.workspace.autograders import ensure_extracted, list_autograders
from GAVEL.app.workspace.layout import CourseKey, Workspace

KEY = CourseKey.parse("ser334_25fc_82931")


def _zip(path: Path, files: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)


def test_nothing_is_listed_for_a_course_without_autograders(tmp_path):
    assert list_autograders(Workspace(tmp_path), KEY, 9) == ()


def test_folders_for_the_module_come_first_then_the_course_zips_newest_first(tmp_path):
    workspace = Workspace(tmp_path)
    root = workspace.course_autograders_dir(KEY)
    (root / "m9" / "hand_placed").mkdir(parents=True)
    (root / "m9" / "older_folder").mkdir()
    (root / "m9" / "stray.txt").write_text("not a folder", encoding="utf-8")
    for name in ("a_grader", "b_grader", "c_grader"):
        _zip(root / f"{name}.zip", {"config.json": "{}"})
    days_old = {
        "m9/hand_placed": 10,
        "m9/older_folder": 30,
        "b_grader.zip": 5,
        "a_grader.zip": 20,
        "c_grader.zip": 20,
    }
    for name, days in days_old.items():
        when = 1_700_000_000 - days * 86_400
        os.utime(root / name, (when, when))

    options = list_autograders(workspace, KEY, 9)

    # Same age falls back to the name, so a_grader sits before c_grader.
    assert [(o.name, o.is_zip) for o in options] == [
        ("hand_placed", False),
        ("older_folder", False),
        ("b_grader", True),
        ("a_grader", True),
        ("c_grader", True),
    ]
    assert list_autograders(workspace, KEY, 3) == options[2:]


def test_a_zip_is_extracted_into_the_module_folder_without_its_wrapper(tmp_path):
    workspace = Workspace(tmp_path)
    root = workspace.course_autograders_dir(KEY)
    _zip(
        root / "grader.zip",
        {"grader/config.json": json.dumps({"files_required": []}), "grader/src/main.py": "pass\n"},
    )
    [option] = list_autograders(workspace, KEY, 9)

    folder = ensure_extracted(option, workspace, KEY, 9)

    assert folder == root / "m9" / "grader"
    assert (folder / "config.json").is_file()
    assert (folder / "src" / "main.py").read_text(encoding="utf-8") == "pass\n"
    assert [o.is_zip for o in list_autograders(workspace, KEY, 9)] == [False]


def test_a_flat_zip_keeps_its_layout(tmp_path):
    workspace = Workspace(tmp_path)
    root = workspace.course_autograders_dir(KEY)
    _zip(root / "flat.zip", {"config.json": "{}", "main.py": "pass\n", "lib/x.jar": "jar"})
    [option] = list_autograders(workspace, KEY, 3)

    folder = ensure_extracted(option, workspace, KEY, 3)

    assert sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()) == [
        "config.json",
        "lib/x.jar",
        "main.py",
    ]


def test_an_extracted_folder_is_reused_and_a_newer_zip_replaces_it(tmp_path):
    workspace = Workspace(tmp_path)
    root = workspace.course_autograders_dir(KEY)
    _zip(root / "grader.zip", {"config.json": "first"})
    [option] = list_autograders(workspace, KEY, 9)
    folder = ensure_extracted(option, workspace, KEY, 9)
    (folder / "marker").write_text("kept", encoding="utf-8")

    assert ensure_extracted(option, workspace, KEY, 9) == folder
    assert (folder / "marker").is_file()

    _zip(root / "grader.zip", {"config.json": "second"})
    newer = root / "grader.zip"
    newer.touch()
    import os
    import time

    os.utime(newer, (time.time() + 5, time.time() + 5))

    ensure_extracted(option, workspace, KEY, 9)

    assert (folder / "config.json").read_text(encoding="utf-8") == "second"
    assert not (folder / "marker").exists()


def test_a_folder_option_is_used_as_is(tmp_path):
    workspace = Workspace(tmp_path)
    root = workspace.course_autograders_dir(KEY)
    (root / "m9" / "ready").mkdir(parents=True)
    [option] = list_autograders(workspace, KEY, 9)

    assert ensure_extracted(option, workspace, KEY, 9) == root / "m9" / "ready"


def test_zip_entries_that_escape_the_folder_are_skipped(tmp_path):
    workspace = Workspace(tmp_path)
    root = workspace.course_autograders_dir(KEY)
    _zip(root / "evil.zip", {"config.json": "{}", "../outside.txt": "no"})
    [option] = list_autograders(workspace, KEY, 9)

    folder = ensure_extracted(option, workspace, KEY, 9)

    assert (folder / "config.json").is_file()
    assert not (root / "m9" / "outside.txt").exists()
