import pytest

from GAVEL.app.dtos.canvas_course import CanvasQuiz
from GAVEL.app.ports.canvas_client import QuizReportUnavailableError
from GAVEL.app.usecases.download_all_quizzes import (
    DownloadAllQuizzesRequest,
    DownloadAllQuizzesUseCase,
)
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import load_manifest


def course_folder(tmp_path) -> CourseFolder:
    return Workspace(tmp_path).course(CourseKey.parse("ser222_25sc_12345"))


class FakeCanvasClient:
    def __init__(self, quizzes, responses):
        self.quizzes = quizzes
        self.responses = responses
        self.attempted_quiz_ids = []

    def list_quizzes(self, course_id):
        return self.quizzes

    def fetch_quiz_student_analysis(self, course_id, quiz_id):
        self.attempted_quiz_ids.append(quiz_id)

        response = self.responses[quiz_id]

        if isinstance(response, Exception):
            raise response

        return response


def test_all_quizzes_download_successfully(tmp_path):
    client = FakeCanvasClient(
        quizzes=[
            CanvasQuiz(id=101, name="Quiz One"),
            CanvasQuiz(id=202, name="Quiz Two"),
        ],
        responses={
            101: b"student,score\nA,10\n",
            202: b"student,score\nB,9\n",
        },
    )

    result = DownloadAllQuizzesUseCase(client).execute(
        DownloadAllQuizzesRequest(
            course_id=123,
            folder=course_folder(tmp_path),
        )
    )

    assert len(result.succeeded) == 2
    assert len(result.skipped) == 0
    assert len(result.failed) == 0

    folder = course_folder(tmp_path)
    assert folder.original.quiz_csv(101).read_bytes() == b"student,score\nA,10\n"
    assert folder.original.quiz_csv(202).exists()
    manifest = load_manifest(folder.manifest_path)
    entry = manifest.artifact("original/quizzes/101.csv")
    assert entry is not None and entry.kind == "quiz"
    assert entry.source_id == 101 and entry.label == "Quiz One"
    assert manifest.canvas_course_id == 123


def test_quiz_already_in_the_folder_is_skipped_not_overwritten(tmp_path):
    client = FakeCanvasClient(
        quizzes=[CanvasQuiz(id=101, name="Quiz One")], responses={101: b"first\n"}
    )
    request = DownloadAllQuizzesRequest(course_id=123, folder=course_folder(tmp_path))
    DownloadAllQuizzesUseCase(client).execute(request)
    client.responses[101] = b"second\n"

    result = DownloadAllQuizzesUseCase(client).execute(request)

    assert result.succeeded == ()
    assert len(result.skipped) == 1 and "already downloaded" in result.skipped[0].skipped_reason
    assert course_folder(tmp_path).original.quiz_csv(101).read_bytes() == b"first\n"
    assert client.attempted_quiz_ids == [101]


def test_unavailable_report_is_skipped_and_batch_continues(tmp_path):
    client = FakeCanvasClient(
        quizzes=[
            CanvasQuiz(id=101, name="Quiz One"),
            CanvasQuiz(id=202, name="Quiz Two"),
            CanvasQuiz(id=303, name="Quiz Three"),
        ],
        responses={
            101: b"one",
            202: QuizReportUnavailableError("No report available"),
            303: b"three",
        },
    )

    result = DownloadAllQuizzesUseCase(client).execute(
        DownloadAllQuizzesRequest(
            course_id=123,
            folder=course_folder(tmp_path),
        )
    )

    assert len(result.succeeded) == 2
    assert len(result.skipped) == 1
    assert len(result.failed) == 0

    assert result.skipped[0].quiz_id == 202
    assert result.skipped[0].skipped_reason == "No report available"

    assert client.attempted_quiz_ids == [101, 202, 303]


def test_failure_does_not_stop_batch(tmp_path):
    client = FakeCanvasClient(
        quizzes=[
            CanvasQuiz(id=101, name="Quiz One"),
            CanvasQuiz(id=202, name="Quiz Two"),
            CanvasQuiz(id=303, name="Quiz Three"),
        ],
        responses={
            101: b"one",
            202: RuntimeError("Canvas exploded"),
            303: b"three",
        },
    )

    result = DownloadAllQuizzesUseCase(client).execute(
        DownloadAllQuizzesRequest(
            course_id=123,
            folder=course_folder(tmp_path),
        )
    )

    assert len(result.succeeded) == 2
    assert len(result.skipped) == 0
    assert len(result.failed) == 1

    assert result.failed[0].quiz_id == 202
    assert "Canvas exploded" in result.failed[0].error

    assert client.attempted_quiz_ids == [101, 202, 303]


def test_invalid_course_id_raises_value_error(tmp_path):
    client = FakeCanvasClient(quizzes=[], responses={})

    with pytest.raises(ValueError):
        DownloadAllQuizzesUseCase(client).execute(
            DownloadAllQuizzesRequest(
                course_id=0,
                folder=course_folder(tmp_path),
            )
        )


def test_empty_quiz_list_returns_empty_result(tmp_path):
    client = FakeCanvasClient(quizzes=[], responses={})

    result = DownloadAllQuizzesUseCase(client).execute(
        DownloadAllQuizzesRequest(
            course_id=123,
            folder=course_folder(tmp_path),
        )
    )

    assert result.outcomes == ()
    assert result.succeeded == ()
    assert result.skipped == ()
    assert result.failed == ()
