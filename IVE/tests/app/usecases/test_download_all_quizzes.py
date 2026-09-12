import pytest

from GAVEL.app.dtos.canvas_course import CanvasQuiz
from GAVEL.app.ports.canvas_client import QuizReportUnavailableError
from GAVEL.app.usecases.download_all_quizzes import (
    DownloadAllQuizzesRequest,
    DownloadAllQuizzesUseCase,
)


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
            output_dir=tmp_path,
        )
    )

    assert len(result.succeeded) == 2
    assert len(result.skipped) == 0
    assert len(result.failed) == 0

    assert (tmp_path / "Quiz_One_101.csv").exists()
    assert (tmp_path / "Quiz_Two_202.csv").exists()


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
            output_dir=tmp_path,
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
            output_dir=tmp_path,
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
                output_dir=tmp_path,
            )
        )


def test_empty_quiz_list_returns_empty_result(tmp_path):
    client = FakeCanvasClient(quizzes=[], responses={})

    result = DownloadAllQuizzesUseCase(client).execute(
        DownloadAllQuizzesRequest(
            course_id=123,
            output_dir=tmp_path,
        )
    )

    assert result.outcomes == ()
    assert result.succeeded == ()
    assert result.skipped == ()
    assert result.failed == ()