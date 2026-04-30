"""
Unit tests for DownloadConsentFormUseCase using a mock CanvasClient.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasCourseData
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.usecases.download_consent_form import (
    DownloadConsentFormRequest,
    DownloadConsentFormUseCase,
)

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

COURSE_ID = 253450
QUIZ_ID = 1960789

CONSENT_CSV_BYTES = (
    b"name,id,sis_id,section,section_id,section_sis_id,submitted,attempt,"
    b'"29684859: Name: (leave blank if you do not consent)",0.0,'
    b'"29684860: Do you consent to be included in the study?",0.0,'
    b"n correct,n incorrect,score\n"
    b"Lindy Crain,494030,1219749063,TRN-2026Spring-IVECapstone,385739,"
    b"TRN-2026Spring-1770947129529_section_main,2026-04-09 03:28:49 UTC,1,"
    b"Lindy Crain,0.0,True,0.0,2,0,0.0\n"
)


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------


class MockCanvasClient(CanvasClient):
    def __init__(self) -> None:
        self.consent_csv: bytes | None = CONSENT_CSV_BYTES
        self.fetch_quiz_error: Exception | None = None
        self.fetch_quiz_calls: list[tuple[int, int]] = []

    def list_courses(self) -> list:
        return []

    def fetch_course_data(self, course_id: int) -> CanvasCourseData:
        raise NotImplementedError

    def fetch_gradebook(self, course_id: int) -> CanvasGradebook:
        raise NotImplementedError

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        raise NotImplementedError

    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
        self.fetch_quiz_calls.append((course_id, quiz_id))
        if self.fetch_quiz_error:
            raise self.fetch_quiz_error
        if self.consent_csv is None:
            raise FileNotFoundError(f"Quiz {quiz_id} not found in course {course_id}")
        return self.consent_csv

    def list_quizzes(self, course_id: int) -> list:
        return []

    def list_assignments(self, course_id: int) -> list:
        return []

    def fetch_rubric_assessments(
        self, course_id: int, assignment_id: int
    ) -> list[RubricAssessment]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> MockCanvasClient:
    return MockCanvasClient()


@pytest.fixture
def use_case(client: MockCanvasClient) -> DownloadConsentFormUseCase:
    return DownloadConsentFormUseCase(canvas_client=client)


@pytest.fixture
def request_(tmp_path: Path) -> DownloadConsentFormRequest:
    return DownloadConsentFormRequest(
        course_id=COURSE_ID,
        quiz_id=QUIZ_ID,
        output_dir=tmp_path,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_execute_returns_result(self, use_case, request_):
        result = use_case.execute(request_)
        assert result is not None

    def test_output_file_is_created(self, use_case, request_, tmp_path):
        use_case.execute(request_)
        assert (tmp_path / f"consent_form_{COURSE_ID}.csv").exists()

    def test_output_filename_contains_course_id(self, use_case, request_, tmp_path):
        use_case.execute(request_)
        assert (tmp_path / f"consent_form_{COURSE_ID}.csv").exists()

    def test_output_content_matches(self, use_case, request_, tmp_path):
        use_case.execute(request_)
        path = tmp_path / f"consent_form_{COURSE_ID}.csv"
        assert path.read_bytes() == CONSENT_CSV_BYTES

    def test_fetched_with_correct_ids(self, use_case, request_, client):
        use_case.execute(request_)
        assert (COURSE_ID, QUIZ_ID) in client.fetch_quiz_calls

    def test_result_message_contains_course_id(self, use_case, request_):
        result = use_case.execute(request_)
        assert str(COURSE_ID) in result.message

    def test_result_saved_path_matches_output_file(self, use_case, request_, tmp_path):
        result = use_case.execute(request_)
        assert result.saved_path == tmp_path / f"consent_form_{COURSE_ID}.csv"

    def test_output_dir_is_created_if_missing(self, use_case, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        request_ = DownloadConsentFormRequest(
            course_id=COURSE_ID,
            quiz_id=QUIZ_ID,
            output_dir=nested,
        )
        use_case.execute(request_)
        assert nested.exists()


# ---------------------------------------------------------------------------
# Missing consent form
# ---------------------------------------------------------------------------


class TestMissingConsentForm:
    def test_raises_when_quiz_not_found(self, use_case, request_, client):
        client.consent_csv = None
        with pytest.raises(FileNotFoundError):
            use_case.execute(request_)

    def test_error_message_contains_quiz_id(self, use_case, request_, client):
        client.consent_csv = None
        with pytest.raises(FileNotFoundError) as exc_info:
            use_case.execute(request_)
        assert str(QUIZ_ID) in str(exc_info.value)

    def test_error_message_contains_course_id(self, use_case, request_, client):
        client.consent_csv = None
        with pytest.raises(FileNotFoundError) as exc_info:
            use_case.execute(request_)
        assert str(COURSE_ID) in str(exc_info.value)

    def test_fetch_was_attempted(self, use_case, request_, client):
        client.consent_csv = None
        with pytest.raises(FileNotFoundError):
            use_case.execute(request_)
        assert len(client.fetch_quiz_calls) == 1


# ---------------------------------------------------------------------------
# API errors
# ---------------------------------------------------------------------------


class TestApiErrors:
    def test_timeout_propagates(self, use_case, request_, client):
        client.fetch_quiz_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError, match="network timeout"):
            use_case.execute(request_)

    def test_unauthorized_propagates(self, use_case, request_, client):
        client.fetch_quiz_error = PermissionError("401 Unauthorized")
        with pytest.raises(PermissionError, match="401"):
            use_case.execute(request_)

    def test_no_file_written_on_error(self, use_case, request_, client, tmp_path):
        client.fetch_quiz_error = TimeoutError("network timeout")
        with pytest.raises(TimeoutError):
            use_case.execute(request_)
        assert not any(tmp_path.rglob("*.csv"))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_raises_for_zero_course_id(self, use_case, tmp_path):
        with pytest.raises(ValueError, match="course_id must be greater than zero"):
            use_case.execute(
                DownloadConsentFormRequest(
                    course_id=0,
                    quiz_id=QUIZ_ID,
                    output_dir=tmp_path,
                )
            )

    def test_raises_for_negative_course_id(self, use_case, tmp_path):
        with pytest.raises(ValueError, match="course_id must be greater than zero"):
            use_case.execute(
                DownloadConsentFormRequest(
                    course_id=-1,
                    quiz_id=QUIZ_ID,
                    output_dir=tmp_path,
                )
            )

    def test_raises_for_zero_quiz_id(self, use_case, tmp_path):
        with pytest.raises(ValueError, match="quiz_id must be greater than zero"):
            use_case.execute(
                DownloadConsentFormRequest(
                    course_id=COURSE_ID,
                    quiz_id=0,
                    output_dir=tmp_path,
                )
            )

    def test_raises_for_negative_quiz_id(self, use_case, tmp_path):
        with pytest.raises(ValueError, match="quiz_id must be greater than zero"):
            use_case.execute(
                DownloadConsentFormRequest(
                    course_id=COURSE_ID,
                    quiz_id=-1,
                    output_dir=tmp_path,
                )
            )

    def test_client_not_called_for_invalid_request(self, use_case, tmp_path, client):
        with pytest.raises(ValueError):
            use_case.execute(
                DownloadConsentFormRequest(
                    course_id=0,
                    quiz_id=QUIZ_ID,
                    output_dir=tmp_path,
                )
            )
        assert client.fetch_quiz_calls == []
