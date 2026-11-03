from __future__ import annotations

import logging
from datetime import timedelta
from types import SimpleNamespace

import requests

from GAVEL.infra.http_logging import log_http_calls, without_query


def fake_response(url: str, status: int = 200, size: str | None = "2048"):
    headers = {} if size is None else {"Content-Length": size}
    return SimpleNamespace(
        request=SimpleNamespace(method="GET", url=url),
        status_code=status,
        elapsed=timedelta(seconds=0.25),
        headers=headers,
    )


def logged_line(caplog, response) -> str:
    session = requests.Session()
    log_http_calls(session)
    with caplog.at_level(logging.INFO, logger="GAVEL.http"):
        for hook in session.hooks["response"]:
            hook(response)
    return caplog.records[-1].getMessage()


def test_logs_method_url_status_time_and_size(caplog):
    line = logged_line(caplog, fake_response("https://canvas.asu.edu/api/v1/courses/1/quizzes"))

    assert line == "GET https://canvas.asu.edu/api/v1/courses/1/quizzes -> 200 (0.25 s, 2.0 KB)"


def test_size_is_left_out_when_the_server_does_not_send_one(caplog):
    line = logged_line(caplog, fake_response("https://canvas.asu.edu/x", size=None))

    assert line == "GET https://canvas.asu.edu/x -> 200 (0.25 s)"


def test_query_string_is_never_logged(caplog):
    signed = "https://files.instructure.com/report.csv?verifier=secret&X-Amz-Signature=abc"

    line = logged_line(caplog, fake_response(signed))

    assert "secret" not in line and "Signature" not in line
    assert without_query(signed) == "https://files.instructure.com/report.csv"


def test_sessions_without_hooks_are_left_alone():
    fake = SimpleNamespace()

    log_http_calls(fake)

    assert not hasattr(fake, "hooks")
