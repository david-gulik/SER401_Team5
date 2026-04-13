from __future__ import annotations

from unittest.mock import patch

import pytest

from GAVEL.infra.canvas.http_canvas_client import CanvasApiConfig, HttpCanvasClient


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

    def request(self, method, url, headers=None, data=None, params=None, json=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "data": data,
                "params": params,
                "json": json,
            }
        )
        if not self._responses:
            raise AssertionError("No more fake responses available")
        return self._responses.pop(0)

    def get(self, url, headers=None, params=None):
        return self.request("GET", url, headers=headers, params=params)

    def post(self, url, headers=None, data=None, json=None):
        return self.request("POST", url, headers=headers, data=data, json=json)


def make_client(session: FakeSession) -> HttpCanvasClient:
    config = CanvasApiConfig(
        base_url="https://canvas.example.com",
        token="fake-token",
        account_id=123,
        poll_interval_seconds=0.0,
        export_timeout_seconds=1.0,
    )
    return HttpCanvasClient(config=config, session=session)


def test_fetch_gradebook_csv_builds_csv_from_grouped_submissions():
    session = FakeSession(
        [
            FakeResponse(
                json_data=[
                    {
                        "user": {"name": "Jane Doe", "id": 1},
                        "user_id": 1,
                    }
                ]
            ),
            FakeResponse(json_data=[{"id": 100, "name": "Section 1"}]),
            FakeResponse(
                json_data=[
                    {
                        "name": "Activities",
                        "position": 1,
                        "assignments": [
                            {
                                "id": 10,
                                "name": "Assignment A",
                                "position": 1,
                            },
                            {
                                "id": 11,
                                "name": "Assignment B",
                                "position": 2,
                            },
                        ],
                    }
                ]
            ),
            FakeResponse(
                json_data=[
                    {
                        "user_id": 1,
                        "computed_final_score": 95.0,
                        "submissions": [
                            {"assignment_id": 10, "score": 40.0},
                            {"assignment_id": 11, "score": 55.0},
                        ],
                    }
                ]
            ),
        ]
    )

    client = make_client(session)
    result = client.fetch_gradebook_csv(course_id=456).decode("utf-8")

    expected_header = (
        "Student Name,Student ID,SIS User ID,SIS Login ID,Section,"
        "Assignment A (10),Assignment B (11),Activities Total,Final Grade"
    )
    assert expected_header in result
    assert "Jane Doe,1,,,,40.0,55.0,95.0,95.0" in result

    assert len(session.calls) == 4
    assert "/enrollments" in session.calls[0]["url"]
    assert "/sections" in session.calls[1]["url"]
    assert "/assignment_groups" in session.calls[2]["url"]
    assert "/students/submissions" in session.calls[3]["url"]
    assert session.calls[3]["params"]["grouped"] == "true"


def test_get_all_pages_follows_next_link():
    session = FakeSession(
        [
            FakeResponse(
                json_data=[{"id": 1}],
                headers={
                    "Link": '<https://canvas.example.com/api/v1/courses/1/enrollments?page=2>; rel="next"'
                },
            ),
            FakeResponse(json_data=[{"id": 2}], headers={}),
        ]
    )

    client = make_client(session)
    result = client._get_all_pages("/api/v1/courses/1/enrollments", params={"per_page": 100})

    assert result == [{"id": 1}, {"id": 2}]
    assert len(session.calls) == 2


def test_build_grouped_submission_lookup_computes_group_totals():
    client = make_client(FakeSession([]))

    assignment_columns = [
        {"assignment_id": 10, "name": "A", "group_name": "Activities"},
        {"assignment_id": 11, "name": "B", "group_name": "Activities"},
        {"assignment_id": 12, "name": "C", "group_name": "Homework"},
    ]

    grouped_submissions = [
        {
            "user_id": 1,
            "computed_final_score": 88.5,
            "submissions": [
                {"assignment_id": 10, "score": 10.0},
                {"assignment_id": 11, "score": 15.5},
                {"assignment_id": 12, "score": 63.0},
            ],
        }
    ]

    result = client._build_grouped_submission_lookup(grouped_submissions, assignment_columns)

    assert result[1]["assignment_scores"][10] == 10.0
    assert result[1]["assignment_scores"][11] == 15.5
    assert result[1]["group_totals"]["Activities"] == 25.5
    assert result[1]["group_totals"]["Homework"] == 63.0
    assert result[1]["computed_final_score"] == 88.5


def test_build_gradebook_columns_sorts_and_skips_omitted_assignments():
    client = make_client(FakeSession([]))

    assignment_groups = [
        {
            "name": "Activities",
            "position": 2,
            "group_weight": 25,
            "assignments": [
                {"id": 22, "name": "Z Activity", "position": 2},
                {"id": 21, "name": "A Activity", "position": 1},
            ],
        },
        {
            "name": "Cairns",
            "position": 1,
            "group_weight": 15,
            "assignments": [
                {"id": 11, "name": "Cairn 1", "position": 1},
                {"id": 12, "name": "Hidden", "position": 2, "omit_from_final_grade": True},
                {"name": "No ID Assignment", "position": 3},
            ],
        },
    ]

    assignment_columns, assignment_group_columns = client._build_gradebook_columns(
        assignment_groups
    )

    assert [col["name"] for col in assignment_group_columns] == [
        "Cairns Total",
        "Activities Total",
    ]
    assert [col["name"] for col in assignment_columns] == [
        "Cairn 1 (11)",
        "A Activity (21)",
        "Z Activity (22)",
    ]


def test_build_grouped_submission_lookup_leaves_none_scores_blank():
    client = make_client(FakeSession([]))

    assignment_columns = [
        {"assignment_id": 10, "name": "A", "group_name": "Activities"},
    ]

    grouped_submissions = [
        {
            "user_id": 1,
            "computed_final_score": "",
            "submissions": [
                {"assignment_id": 10, "score": None},
            ],
        }
    ]

    result = client._build_grouped_submission_lookup(grouped_submissions, assignment_columns)

    assert result[1]["assignment_scores"][10] == ""
    assert result[1]["group_totals"] == {}
    assert result[1]["computed_final_score"] == ""


def test_fetch_gradebook_csv_writes_blank_and_weights_rows():
    session = FakeSession(
        [
            FakeResponse(
                json_data=[
                    {
                        "user": {
                            "name": "Jane Doe",
                            "id": 1,
                            "sis_user_id": "S001",
                            "login_id": "jdoe",
                        },
                        "user_id": 1,
                        "course_section_id": 100,
                    }
                ]
            ),
            FakeResponse(json_data=[{"id": 100, "name": "Section 1"}]),
            FakeResponse(
                json_data=[
                    {
                        "name": "Activities",
                        "position": 1,
                        "group_weight": 25,
                        "assignments": [
                            {"id": 10, "name": "Assignment A", "position": 1},
                        ],
                    }
                ]
            ),
            FakeResponse(
                json_data=[
                    {
                        "user_id": 1,
                        "computed_final_score": 40.0,
                        "submissions": [
                            {"assignment_id": 10, "score": 40.0},
                        ],
                    }
                ]
            ),
        ]
    )

    client = make_client(session)
    rows = client.fetch_gradebook_csv(course_id=456).decode("utf-8").splitlines()

    assert rows[0] == (
        "Student Name,Student ID,SIS User ID,SIS Login ID,Section,"
        "Assignment A (10),Activities Total,Final Grade"
    )
    assert rows[1] == ",,,,,,,"
    assert rows[2] == ",,,,,,25,"
    assert rows[3] == "Jane Doe,1,S001,jdoe,Section 1,40.0,40.0,40.0"


def test_request_with_retries_retries_on_429():
    session = FakeSession(
        [
            FakeResponse(status_code=429, headers={"Retry-After": "0"}),
            FakeResponse(json_data={"ok": True}),
        ]
    )

    client = make_client(session)

    with patch("time.sleep") as sleep_mock:
        response = client._request_with_retries(
            method="GET",
            path="/api/v1/courses/1",
            accept="application/json",
        )

    assert response.json() == {"ok": True}
    assert len(session.calls) == 2
    sleep_mock.assert_called_once()


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
