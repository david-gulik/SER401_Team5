from __future__ import annotations

from unittest.mock import patch

import pytest

from GAVEL.infra.canvas.http_canvas_client import (
    CanvasApiConfig,
    HttpCanvasClient,
)


class FakeResponse:
    def __init__(self, json_data=None, content=b"", status_code=200, headers=None):
        self._json_data = json_data
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def request(self, method, url, headers=None, data=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "data": data,
            }
        )
        if not self._responses:
            raise AssertionError("No more fake responses available")
        return self._responses.pop(0)

    def get(self, url, headers=None):
        return self.request("GET", url, headers=headers)

    def post(self, url, headers=None, data=None):
        return self.request("POST", url, headers=headers, data=data)


def make_client(session: FakeSession) -> HttpCanvasClient:
    config = CanvasApiConfig(
        base_url="https://canvas.example.com",
        token="fake-token",
        account_id=123,
        poll_interval_seconds=0.0,
        export_timeout_seconds=1.0,
    )
    return HttpCanvasClient(config=config, session=session)

def test_fetch_gradebook_csv_builds_csv_from_enrollments_and_assignments():
    session = FakeSession(
        [
            FakeResponse(
                json_data=[
                    {
                        "user": {"name": "Jane Doe", "id": 1},
                        "grades": {"final_grade": "95"},
                    }
                ]
            ),
            FakeResponse(
                json_data=[
                    {"id": 10, "name": "Assignment A"},
                    {"id": 11, "name": "Assignment B"},
                ]
            ),
        ]
    )

    client = make_client(session)
    result = client.fetch_gradebook_csv(course_id=456).decode("utf-8")

    expected_header = (
        "Student Name,Student ID,Assignment A,Assignment B,"
        "Activities Total,Cairns Total,Homework (all) Total,"
        "Homework (Gradescope) Total,Final Grade"
    )

    assert expected_header in result
    assert "Jane Doe,1,,,,,,,95" in result
    assert len(session.calls) == 2
    assert session.calls[0]["method"] == "GET"
    assert "/enrollments" in session.calls[0]["url"]
    assert "/assignments" in session.calls[1]["url"]

TEST_COURSE_ID = 101
TEST_QUIZ_ID = 5
TEST_REPORT_ID = 98765
TEST_CSV_BYTES = b"name,sis_id,attempt\nDalinar Kholin,309780,1"


@pytest.fixture
def config() -> CanvasApiConfig:
    return CanvasApiConfig(
        base_url="https://canvas.asu.edu",
        token="test-token",
        account_id=123,
        poll_interval_seconds=0.0,
        export_timeout_seconds=1.0,
    )


@pytest.fixture
def client(config: CanvasApiConfig) -> HttpCanvasClient:
    return HttpCanvasClient(config)


class TestFetchQuizStudentAnalysis:
    def test_returns_bytes(self, client: HttpCanvasClient) -> None:
        with (
            patch.object(client, "_post") as test_post,
            patch.object(client, "_poll_progress"),
            patch.object(client, "_get") as test_get,
            patch.object(client, "_download") as test_download,
        ):
            test_post.return_value = {
                "id": TEST_REPORT_ID,
                "progress_url": "https://canvas.asu.edu/api/v1/progress/111",
                "workflow_state": "generated",
            }
            test_get.return_value = {
                "id": TEST_REPORT_ID,
                "file": {"url": "https://canvas.asu.edu/files/123/download"},
            }
            test_download.return_value = TEST_CSV_BYTES

            result = client.fetch_quiz_student_analysis(TEST_COURSE_ID, TEST_QUIZ_ID)

            assert isinstance(result, bytes)
            assert result == TEST_CSV_BYTES

    def test_polls_when_progress_url_present(self, client: HttpCanvasClient) -> None:
        with (
            patch.object(client, "_post") as test_post,
            patch.object(client, "_poll_progress") as test_poll,
            patch.object(client, "_get"),
            patch.object(client, "_download") as test_download,
        ):
            test_post.return_value = {
                "id": TEST_REPORT_ID,
                "progress_url": "https://canvas.asu.edu/api/v1/progress/111",
            }
            test_download.return_value = TEST_CSV_BYTES

            client.fetch_quiz_student_analysis(TEST_COURSE_ID, TEST_QUIZ_ID)

            test_poll.assert_called_once()

    def test_skips_poll_when_no_progress_url(self, client: HttpCanvasClient) -> None:
        with (
            patch.object(client, "_post") as test_post,
            patch.object(client, "_poll_progress") as test_poll,
            patch.object(client, "_get"),
            patch.object(client, "_download") as test_download,
        ):
            test_post.return_value = {
                "id": TEST_REPORT_ID,
            }
            test_download.return_value = TEST_CSV_BYTES

            client.fetch_quiz_student_analysis(TEST_COURSE_ID, TEST_QUIZ_ID)

            test_poll.assert_not_called()


class TestPollProgress:
    def test_returns_when_completed(self, client: HttpCanvasClient) -> None:
        with patch.object(client, "_get") as test_get:
            test_get.return_value = {"workflow_state": "completed"}
            client._poll_progress("https://canvas.asu.edu/api/v1/progress/1")

    def test_raises_on_failed(self, client: HttpCanvasClient) -> None:
        with patch.object(client, "_get") as test_get:
            test_get.return_value = {"workflow_state": "failed"}
            with pytest.raises(RuntimeError, match="failed"):
                client._poll_progress("https://canvas.asu.edu/api/v1/progress/1")

    def test_raises_on_timeout(self, client: HttpCanvasClient) -> None:
        with patch.object(client, "_get") as test_get, patch("time.sleep"):
            test_get.return_value = {"workflow_state": "running"}
            with pytest.raises(RuntimeError, match="timed out"):
                client._poll_progress(
                    "https://canvas.asu.edu/api/v1/progress/1",
                    max_attempts=3,
                )
