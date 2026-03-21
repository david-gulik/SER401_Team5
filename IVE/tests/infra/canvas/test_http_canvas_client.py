"""Tests for HttpCanvasClient (infra/canvas adapter)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from GAVEL.infra.canvas.http_canvas_client import (
    CanvasApiConfig,
    HttpCanvasClient,
)

TEST_COURSE_ID = 101
TEST_QUIZ_ID = 5
TEST_REPORT_ID = 98765
TEST_CSV_BYTES = b"name,sis_id,attempt\nDalinar Kholin,309780,1"


@pytest.fixture
def config() -> CanvasApiConfig:
    return CanvasApiConfig(
        base_url="https://canvas.asu.edu",
        token="test-token",
    )


@pytest.fixture
def client(config: CanvasApiConfig) -> HttpCanvasClient:
    return HttpCanvasClient(config)


class TestFetchQuizStudentAnalysis:

    def test_returns_bytes(self, client: HttpCanvasClient) -> None:
        with patch.object(client, "_post") as test_post, \
             patch.object(client, "_poll_progress"), \
             patch.object(client, "_get") as test_get, \
             patch.object(client, "_download") as test_download:

            test_post.return_value = {
                "id": TEST_REPORT_ID,
                "progress_url": "https://canvas.asu.edu/api/v1/progress/111",
                "workflow_state": "generated",
            }
            test_get.return_value = {
                "id": TEST_REPORT_ID,
                "file": {
                    "url": "https://canvas.asu.edu/files/123/download"
                }
            }
            test_download.return_value = TEST_CSV_BYTES

            result = client.fetch_quiz_student_analysis(
                TEST_COURSE_ID, TEST_QUIZ_ID
            )

            assert isinstance(result, bytes)
            assert result == TEST_CSV_BYTES

    def test_polls_when_progress_url_present(
        self, client: HttpCanvasClient
    ) -> None:
        with patch.object(client, "_post") as test_post, \
             patch.object(client, "_poll_progress") as test_poll, \
             patch.object(client, "_get"), \
             patch.object(client, "_download") as test_download:

            test_post.return_value = {
                "id": TEST_REPORT_ID,
                "progress_url": "https://canvas.asu.edu/api/v1/progress/111",
            }
            test_download.return_value = TEST_CSV_BYTES

            client.fetch_quiz_student_analysis(
                TEST_COURSE_ID, TEST_QUIZ_ID
            )

            test_poll.assert_called_once()

    def test_skips_poll_when_no_progress_url(
        self, client: HttpCanvasClient
    ) -> None:
        with patch.object(client, "_post") as test_post, \
             patch.object(client, "_poll_progress") as test_poll, \
             patch.object(client, "_get"), \
             patch.object(client, "_download") as test_download:

            test_post.return_value = {
                "id": TEST_REPORT_ID,
            }
            test_download.return_value = TEST_CSV_BYTES

            client.fetch_quiz_student_analysis(
                TEST_COURSE_ID, TEST_QUIZ_ID
            )

            test_poll.assert_not_called()


class TestPollProgress:

    def test_returns_when_completed(
        self, client: HttpCanvasClient
    ) -> None:
        with patch.object(client, "_get") as test_get:
            test_get.return_value = {"workflow_state": "completed"}
            client._poll_progress("https://canvas.asu.edu/api/v1/progress/1")

    def test_raises_on_failed(
        self, client: HttpCanvasClient
    ) -> None:
        with patch.object(client, "_get") as test_get:
            test_get.return_value = {"workflow_state": "failed"}
            with pytest.raises(RuntimeError, match="failed"):
                client._poll_progress(
                    "https://canvas.asu.edu/api/v1/progress/1"
                )

    def test_raises_on_timeout(
        self, client: HttpCanvasClient
    ) -> None:
        with patch.object(client, "_get") as test_get, \
             patch("time.sleep"):
            test_get.return_value = {"workflow_state": "running"}
            with pytest.raises(RuntimeError, match="timed out"):
                client._poll_progress(
                    "https://canvas.asu.edu/api/v1/progress/1",
                    max_attempts=3,
                )