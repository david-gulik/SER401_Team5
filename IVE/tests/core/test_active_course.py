from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import QSettings

from GAVEL.app.workspace.layout import CourseFolder, Workspace
from GAVEL.core.active_course import ActiveCourse

FIRST = "ser222_26f_11111"
SECOND = "ser316_26s_33333"


def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "gavel.ini"), QSettings.Format.IniFormat)


def course(tmp_path: Path, folder_name: str) -> CourseFolder:
    folder = tmp_path / "courses" / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    return Workspace(tmp_path).list_courses()[
        [c.key.folder_name for c in Workspace(tmp_path).list_courses()].index(folder_name)
    ]


def test_starts_with_no_course_when_nothing_was_remembered(qapp, tmp_path):
    active = ActiveCourse(Workspace(tmp_path), settings(tmp_path))

    assert active.course is None


def test_select_notifies_subscribers(qapp, tmp_path):
    first = course(tmp_path, FIRST)
    active = ActiveCourse(Workspace(tmp_path), settings(tmp_path))
    received: list[CourseFolder | None] = []
    active.changed.connect(received.append)

    active.select(first)

    assert active.course == first
    assert received == [first]


def test_selecting_the_same_course_again_is_silent(qapp, tmp_path):
    first = course(tmp_path, FIRST)
    active = ActiveCourse(Workspace(tmp_path), settings(tmp_path))
    received: list[CourseFolder | None] = []
    active.changed.connect(received.append)

    active.select(first)
    active.select(first)

    assert received == [first]


def test_select_none_clears_the_course_and_notifies(qapp, tmp_path):
    first = course(tmp_path, FIRST)
    active = ActiveCourse(Workspace(tmp_path), settings(tmp_path))
    active.select(first)
    received: list[CourseFolder | None] = []
    active.changed.connect(received.append)

    active.select(None)

    assert active.course is None
    assert received == [None]


def test_the_pick_is_remembered_for_the_next_launch(qapp, tmp_path):
    second = course(tmp_path, SECOND)
    course(tmp_path, FIRST)
    ActiveCourse(Workspace(tmp_path), settings(tmp_path)).select(second)

    relaunched = ActiveCourse(Workspace(tmp_path), settings(tmp_path))

    assert relaunched.course == second


def test_a_remembered_course_whose_folder_is_gone_restores_as_none(qapp, tmp_path):
    first = course(tmp_path, FIRST)
    ActiveCourse(Workspace(tmp_path), settings(tmp_path)).select(first)
    shutil.rmtree(first.path)

    relaunched = ActiveCourse(Workspace(tmp_path), settings(tmp_path))

    assert relaunched.course is None


def test_revalidate_drops_a_course_deleted_while_the_app_runs(qapp, tmp_path):
    first = course(tmp_path, FIRST)
    active = ActiveCourse(Workspace(tmp_path), settings(tmp_path))
    active.select(first)
    received: list[CourseFolder | None] = []
    active.changed.connect(received.append)
    shutil.rmtree(first.path)

    active.revalidate()

    assert active.course is None
    assert received == [None]


def test_revalidate_keeps_a_course_that_is_still_there(qapp, tmp_path):
    first = course(tmp_path, FIRST)
    active = ActiveCourse(Workspace(tmp_path), settings(tmp_path))
    active.select(first)
    received: list[CourseFolder | None] = []
    active.changed.connect(received.append)

    active.revalidate()

    assert active.course == first
    assert received == []
