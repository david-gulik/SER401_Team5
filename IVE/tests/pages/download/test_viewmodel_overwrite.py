"""Re-downloading files already in the course folder: the overwrite prompt and its answers."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourse, CanvasQuiz
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import load_manifest
from GAVEL.core.status import Status
from GAVEL.pages.download.viewmodel import (
    AskOverwrite,
    DownloadViewModel,
    OverwriteChoice,
    ShowError,
    ShowInfo,
)
from GAVEL.services.logger import AppLogger
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient
from tests.pages.download.test_viewmodel_roster import wait_for_workers

COURSE = CanvasCourse(id=273116, name="SER 402", course_code="2026FallC-X-SER402-87275")
QUIZZES = [CanvasQuiz(id=101, name="Quiz One"), CanvasQuiz(id=202, name="Quiz Two")]
GRADEBOOK = "original/gradebook.csv"


class CountingCanvasClient(FakeCanvasClient):
    """Serves the gradebook and quiz reports, numbering each fetch so a replaced file shows it."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.gradebook_fetches = 0
        self.quiz_fetches: list[int] = []

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        self.gradebook_fetches += 1
        return f"Student,ID\nfetch {self.gradebook_fetches},1\n".encode()

    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
        self.quiz_fetches.append(quiz_id)
        if quiz_id not in {q.id for q in self.quizzes}:
            raise RuntimeError(f"no quiz {quiz_id}")
        return f"student,score\nfetch {len(self.quiz_fetches)},1\n".encode()


@pytest.fixture
def canvas() -> CountingCanvasClient:
    return CountingCanvasClient(courses=[COURSE], quizzes=QUIZZES)


@pytest.fixture
def roster() -> FakeRosterClient:
    return FakeRosterClient()


@pytest.fixture
def vm(qapp, canvas, roster, tmp_path: Path) -> DownloadViewModel:
    vm = DownloadViewModel(
        roster_client=roster,
        canvas_client=canvas,
        default_output_dir=tmp_path,
        logger=AppLogger("test"),
        roster_configured=True,
    )
    vm.load_courses()
    wait_for_workers(qapp)
    vm.set_course_id(str(COURSE.id))
    return vm


@pytest.fixture
def events(vm: DownloadViewModel) -> list[object]:
    seen: list[object] = []
    vm.event_raised.connect(seen.append)
    return seen


@pytest.fixture
def folder(tmp_path: Path) -> CourseFolder:
    key = CourseKey.from_canvas_course_code(COURSE.course_code)
    assert key is not None
    return Workspace(tmp_path).course(key)


def run(qapp, action) -> None:
    action()
    wait_for_workers(qapp)


def asks(events: list[object]) -> list[AskOverwrite]:
    return [e for e in events if isinstance(e, AskOverwrite)]


class TestSingleFile:
    def test_existing_file_asks_instead_of_stopping(self, qapp, vm, events, canvas) -> None:
        run(qapp, vm.download_gradebook)
        events.clear()

        run(qapp, vm.download_gradebook)

        assert events == [AskOverwrite((GRADEBOOK,))]
        assert canvas.gradebook_fetches == 1
        assert vm.get_state().status is Status.WARNING

    def test_skip_keeps_the_file_and_shows_why(self, qapp, vm, events, canvas, folder) -> None:
        run(qapp, vm.download_gradebook)
        run(qapp, vm.download_gradebook)
        events.clear()

        vm.answer_overwrite(OverwriteChoice.SKIP)
        wait_for_workers(qapp)

        assert len(events) == 1 and isinstance(events[0], ShowInfo)
        assert "already downloaded" in events[0].message
        assert canvas.gradebook_fetches == 1
        assert "fetch 1" in folder.original.gradebook_csv.read_text(encoding="utf-8")

    def test_overwrite_once_replaces_and_asks_again_next_time(
        self, qapp, vm, events, canvas, folder
    ) -> None:
        run(qapp, vm.download_gradebook)
        run(qapp, vm.download_gradebook)

        vm.answer_overwrite(OverwriteChoice.ONCE)
        wait_for_workers(qapp)

        assert canvas.gradebook_fetches == 2
        assert "fetch 2" in folder.original.gradebook_csv.read_text(encoding="utf-8")
        assert not vm.get_state().overwrite_session
        entry = load_manifest(folder.manifest_path).artifact(GRADEBOOK)
        assert entry is not None and entry.sha256

        events.clear()
        run(qapp, vm.download_gradebook)
        assert asks(events) == [AskOverwrite((GRADEBOOK,))]

    def test_overwrite_for_session_stops_asking(self, qapp, vm, events, canvas, folder) -> None:
        run(qapp, vm.download_gradebook)
        run(qapp, vm.download_gradebook)

        vm.answer_overwrite(OverwriteChoice.SESSION)
        wait_for_workers(qapp)
        assert vm.get_state().overwrite_session
        assert canvas.gradebook_fetches == 2

        events.clear()
        run(qapp, vm.download_gradebook)

        assert asks(events) == []
        assert canvas.gradebook_fetches == 3
        assert "fetch 3" in folder.original.gradebook_csv.read_text(encoding="utf-8")

    def test_turning_session_overwrite_off_asks_again(self, qapp, vm, events) -> None:
        vm.set_overwrite_session(True)
        run(qapp, vm.download_gradebook)
        run(qapp, vm.download_gradebook)
        assert asks(events) == []

        vm.set_overwrite_session(False)
        run(qapp, vm.download_gradebook)

        assert asks(events) == [AskOverwrite((GRADEBOOK,))]

    def test_file_deleted_from_disk_downloads_again_without_asking(
        self, qapp, vm, events, canvas, folder
    ) -> None:
        run(qapp, vm.download_gradebook)
        folder.original.gradebook_csv.unlink()
        events.clear()

        run(qapp, vm.download_gradebook)

        assert asks(events) == []
        assert canvas.gradebook_fetches == 2
        assert folder.original.gradebook_csv.is_file()

    def test_an_answer_with_nothing_pending_does_nothing(self, qapp, vm, events, canvas) -> None:
        vm.answer_overwrite(OverwriteChoice.ONCE)
        wait_for_workers(qapp)
        assert events == [] and canvas.gradebook_fetches == 0


class TestQuizBatch:
    def test_asks_once_and_retries_only_the_refused_quizzes(self, qapp, vm, events, canvas) -> None:
        run(qapp, vm.download_all_quizzes)
        canvas.quizzes.append(CanvasQuiz(id=303, name="Quiz Three"))
        canvas.quiz_fetches.clear()
        events.clear()

        run(qapp, vm.download_all_quizzes)

        assert canvas.quiz_fetches == [303]
        assert events == [AskOverwrite(("original/quizzes/101.csv", "original/quizzes/202.csv"))]

        vm.answer_overwrite(OverwriteChoice.ONCE)
        wait_for_workers(qapp)

        assert canvas.quiz_fetches == [303, 101, 202]
        assert "2 saved" in vm.get_state().message

    def test_deleted_quiz_report_is_fetched_without_asking(
        self, qapp, vm, events, canvas, folder
    ) -> None:
        run(qapp, vm.download_all_quizzes)
        folder.original.quiz_csv(101).unlink()
        canvas.quiz_fetches.clear()
        events.clear()

        run(qapp, vm.download_all_quizzes)

        assert canvas.quiz_fetches == [101]
        assert events == [AskOverwrite(("original/quizzes/202.csv",))]


class TestDownloadAll:
    @pytest.fixture(autouse=True)
    def no_gradescope(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Without credentials the Gradescope step fails fast instead of opening a browser.
        monkeypatch.delenv("CANVAS_USERNAME", raising=False)
        monkeypatch.delenv("CANVAS_PASSWORD", raising=False)

    @pytest.fixture
    def ready(self, vm: DownloadViewModel) -> DownloadViewModel:
        vm.set_term("2267")
        vm.set_class_number("87275")
        vm.set_consent_quiz_id("11")  # not a listed quiz, so the consent step fails
        return vm

    def test_asks_once_for_the_whole_batch(self, qapp, ready, events, canvas, roster) -> None:
        run(qapp, ready.download_all)
        events.clear()

        run(qapp, ready.download_all)

        prompts = asks(events)
        assert len(prompts) == 1
        assert set(prompts[0].paths) == {
            "original/roster.csv",
            GRADEBOOK,
            "original/quizzes/101.csv",
            "original/quizzes/202.csv",
        }
        assert not [e for e in events if isinstance(e, ShowInfo | ShowError)]

    def test_overwrite_reruns_only_the_refused_steps(
        self, qapp, ready, events, canvas, roster
    ) -> None:
        run(qapp, ready.download_all)
        run(qapp, ready.download_all)
        roster_before = len(roster.roster_requests)
        canvas.quiz_fetches.clear()

        ready.answer_overwrite(OverwriteChoice.ONCE)
        wait_for_workers(qapp)

        assert len(roster.roster_requests) == roster_before + 1
        assert canvas.gradebook_fetches == 2
        # The consent form (quiz 11) failed rather than being refused, so it is not retried.
        assert sorted(canvas.quiz_fetches) == [101, 202]
        assert ready.get_state().message.startswith("All downloads complete")

    def test_skip_shows_the_batch_summary(self, qapp, ready, events) -> None:
        run(qapp, ready.download_all)
        run(qapp, ready.download_all)
        events.clear()

        ready.answer_overwrite(OverwriteChoice.SKIP)

        # Gradescope and the consent form failed, so the summary is an error.
        assert len(events) == 1 and isinstance(events[0], ShowError)
        assert events[0].message == ready.get_state().message
