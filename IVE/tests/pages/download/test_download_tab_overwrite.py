"""DownloadTab: the overwrite prompt for files already downloaded, and the session switch."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QPushButton, QWidget

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.pages.download import tabs
from GAVEL.pages.download.overwrite_prompt import MAX_LISTED, overwrite_prompt_text
from GAVEL.pages.download.tabs import OVERWRITE_SESSION_TEXT, DownloadTab
from GAVEL.pages.download.viewmodel import DownloadViewModel, OverwriteChoice
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_viewmodel_roster import wait_for_workers

COURSE = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")


class GradebookCanvasClient(FakeCanvasClient):
    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        self.download_calls.append("fetch_gradebook_csv")
        return b"Student,ID\n"


@pytest.fixture
def env(qapp, theme, tmp_path: Path, monkeypatch) -> SimpleNamespace:
    canvas = GradebookCanvasClient(courses=[COURSE])
    vm = DownloadViewModel(
        roster_client=FakeRosterClient(),
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    answers: list[OverwriteChoice] = []
    asked: list[tuple[str, ...]] = []

    def fake_ask(parent: QWidget, paths: Sequence[str]) -> OverwriteChoice:
        asked.append(tuple(paths))
        return answers.pop(0)

    tab = DownloadTab(theme, vm, ask_overwrite=fake_ask)
    monkeypatch.setattr(tabs, "show_message", lambda *a, **k: None)
    # The course folder is named from the loaded course's code.
    vm.load_courses()
    wait_for_workers(qapp)
    vm.set_course_id(str(COURSE.id))
    return SimpleNamespace(tab=tab, vm=vm, canvas=canvas, answers=answers, asked=asked)


def download_gradebook(qapp, env) -> None:
    env.vm.download_gradebook()
    wait_for_workers(qapp)


def session_row(tab: DownloadTab) -> QWidget:
    return tab._overwrite_session_row


def test_existing_file_shows_the_prompt_and_passes_on_the_answer(qapp, env) -> None:
    download_gradebook(qapp, env)
    env.answers.append(OverwriteChoice.ONCE)

    download_gradebook(qapp, env)
    wait_for_workers(qapp)

    assert env.asked == [("original/gradebook.csv",)]
    assert env.canvas.download_calls.count("fetch_gradebook_csv") == 2


def test_session_row_shows_while_overwrite_is_on_and_turns_it_off(qapp, env) -> None:
    row = session_row(env.tab)
    assert row.isHidden()

    download_gradebook(qapp, env)
    env.answers.append(OverwriteChoice.SESSION)
    download_gradebook(qapp, env)
    wait_for_workers(qapp)

    assert env.vm.get_state().overwrite_session
    assert not row.isHidden()
    assert any(OVERWRITE_SESSION_TEXT == label.text() for label in row.findChildren(tabs.QLabel))

    turn_off = row.findChild(QPushButton)
    turn_off.click()

    assert not env.vm.get_state().overwrite_session
    assert row.isHidden()


class TestPromptText:
    def test_one_file(self) -> None:
        text = overwrite_prompt_text(["original/gradebook.csv"])
        assert text.startswith("1 file is already in the course folder:")
        assert "original/gradebook.csv" in text
        assert "Replace it with a fresh download?" in text

    def test_many_files_are_counted_past_the_limit(self) -> None:
        paths = [f"original/quizzes/{n}.csv" for n in range(MAX_LISTED + 3)]
        text = overwrite_prompt_text(paths)
        assert text.startswith(f"{MAX_LISTED + 3} files are already in the course folder:")
        assert paths[MAX_LISTED - 1] in text and paths[MAX_LISTED] not in text
        assert "and 3 more" in text
        assert "Replace them with a fresh download?" in text
