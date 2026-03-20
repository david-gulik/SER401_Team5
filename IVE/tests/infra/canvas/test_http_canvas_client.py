from __future__ import annotations

import pytest

from IVE.GAVEL.infra.canvas.http_canvas_client import (
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
        self.calls.append({
            "method": method,
            "url": url,
            "headers": headers,
            "data": data,
        })
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


def test_fetch_gradebook_csv_success():
    session = FakeSession([
        FakeResponse(json_data={"id": 99}),  # POST start export
        FakeResponse(json_data={"workflow_state": "running"}),  # poll 1
        FakeResponse(json_data={  # poll 2 complete
            "workflow_state": "complete",
            "file_url": "https://canvas.example.com/file.csv",
        }),
        FakeResponse(content=b"Student,ID\nJane,1\n"),  # download CSV
    ])

    client = make_client(session)

    result = client.fetch_gradebook_csv(course_id=456)

    assert result == b"Student,ID\nJane,1\n"
    assert len(session.calls) == 4
    assert session.calls[0]["method"] == "POST"


def test_fetch_gradebook_csv_failed():
    session = FakeSession([
        FakeResponse(json_data={"id": 99}),
        FakeResponse(json_data={"workflow_state": "failed"}),
    ])

    client = make_client(session)

    with pytest.raises(RuntimeError, match="failed"):
        client.fetch_gradebook_csv(course_id=456)


def test_fetch_gradebook_csv_timeout():
    session = FakeSession([
        FakeResponse(json_data={"id": 99}),
        FakeResponse(json_data={"workflow_state": "running"}),
        FakeResponse(json_data={"workflow_state": "running"}),
    ])

    config = CanvasApiConfig(
        base_url="https://canvas.example.com",
        token="fake-token",
        account_id=123,
        poll_interval_seconds=0.0,
        export_timeout_seconds=0.0,
    )

    client = HttpCanvasClient(config=config, session=session)

    with pytest.raises(TimeoutError):
        client.fetch_gradebook_csv(course_id=456)