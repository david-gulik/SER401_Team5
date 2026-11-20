from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_gradebook import (
    CanvasGradebook,
    GradebookAssignmentColumn,
    GradebookStudentRow,
)
from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.usecases.proxy_grade.generate_r_squared_report import (
    compute_r_squared_report,
    write_r_squared_report,
)

_PROGRAMMING = "M2: Programming (111)"
_QUIZ = "Quiz 3 (222)"


def _submission(key: str, passing: set[str], all_tests: set[str]) -> GradescopeSubmission:
    tests = [
        GradescopeTestScore(name=name, score=1.0 if name in passing else 0.0, max_score=1.0)
        for name in all_tests
    ]
    return GradescopeSubmission(
        submission_key=key,
        submitter=GradescopeSubmitter(sid="1", email="student@example.com", name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests,
    )


def _column(raw_header: str) -> GradebookAssignmentColumn:
    return GradebookAssignmentColumn(
        raw_header=raw_header, canvas_id=1, display_name=raw_header, points_possible=10.0
    )


def _row(canvas_id: int, programming: float, quiz: float) -> GradebookStudentRow:
    return GradebookStudentRow(
        student_name=f"Student {canvas_id}",
        canvas_id=canvas_id,
        sis_login_id=f"student{canvas_id}",
        section="001",
        assignment_scores={_PROGRAMMING: programming, _QUIZ: quiz},
    )


def test_computes_both_checks_independently() -> None:
    all_tests = {"A", "B"}
    submissions = [
        _submission("s1", {"A", "B"}, all_tests),
        _submission("s2", {"A"}, all_tests),
        _submission("s3", set(), all_tests),
    ]
    gradebook = CanvasGradebook(
        columns=(_column(_PROGRAMMING), _column(_QUIZ)),
        rows=(_row(1, 2.0, 4.0), _row(2, 4.0, 8.0), _row(3, 6.0, 12.0)),
    )

    result = compute_r_squared_report(submissions, gradebook, _PROGRAMMING, _QUIZ)

    assert len(result.test_pairs) == 1
    assert result.test_pairs[0].test_a == "A"
    assert result.test_pairs[0].test_b == "B"
    assert result.cross_assessment.column_a == _PROGRAMMING
    assert result.cross_assessment.column_b == _QUIZ
    assert result.cross_assessment.r_squared == pytest.approx(1.0)


def test_writes_the_report_in_its_json_format(tmp_path: Path) -> None:
    all_tests = {"A", "B"}
    submissions = [
        _submission("s1", {"A", "B"}, all_tests),
        _submission("s2", {"A"}, all_tests),
        _submission("s3", set(), all_tests),
    ]
    gradebook = CanvasGradebook(
        columns=(_column(_PROGRAMMING), _column(_QUIZ)),
        rows=(_row(1, 2.0, 4.0), _row(2, 4.0, 8.0), _row(3, 6.0, 12.0)),
    )
    result = compute_r_squared_report(submissions, gradebook, _PROGRAMMING, _QUIZ)
    output_path = tmp_path / "report.json"

    write_r_squared_report(result, output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["test_pairs"] == [
        {"test_a": "A", "test_b": "B", "r_squared": pytest.approx(0.25)}
    ]
    assert payload["cross_assessment"]["column_a"] == _PROGRAMMING
    assert payload["cross_assessment"]["column_b"] == _QUIZ
