from __future__ import annotations

from datetime import UTC, datetime

import pytest

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook, GradebookStudentRow
from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier
from GAVEL.app.dtos.rubric_assessment import RubricAssessment, RubricCriterionScore
from GAVEL.app.dtos.rubric_definition import RubricCriterionDefinition, RubricDefinition
from GAVEL.app.usecases.proxy_grade.generate_heat_map_report import (
    HeatMapScoreRow,
    compute_heat_map_rows,
)

# A small two-criterion mapping, named to match the rubric fixture below.
_MAPPING = ProxyGradeMapping(
    name="toy",
    criteria=(
        Criterion("main menu", (Tier(2.0, all_of=("Test A", "Test B")),)),
        Criterion("memory leaks", (Tier(2.0, all_of=("Test C",)),)),
    ),
)
_ALL_TEST_NAMES = list(_MAPPING.test_names())
_GRADEBOOK_COLUMN = "Module 2: Programming (123456)"


def _rubric_criterion(cid: str, description: str) -> RubricCriterionDefinition:
    return RubricCriterionDefinition(
        id=cid, description=description, long_description="", points=2.0, ratings=()
    )


_RUBRIC = RubricDefinition(
    rubric_id="1",
    title="toy rubric",
    points_possible=4.0,
    free_form_criterion_comments=False,
    criteria=(
        _rubric_criterion("c1", "main menu"),
        _rubric_criterion("c2", "memory leaks"),
    ),
)


def _submission(sid: str, email: str, passing: set[str]) -> GradescopeSubmission:
    tests = [
        GradescopeTestScore(name=name, score=1.0 if name in passing else 0.0, max_score=1.0)
        for name in _ALL_TEST_NAMES
    ]
    return GradescopeSubmission(
        submission_key=f"submission_{sid}",
        submitter=GradescopeSubmitter(sid=sid, email=email, name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests,
    )


def _gradebook_row(canvas_id: int, login: str) -> GradebookStudentRow:
    return GradebookStudentRow(
        student_name="Test, Student",
        canvas_id=canvas_id,
        sis_login_id=login,
        section="001",
        assignment_scores={_GRADEBOOK_COLUMN: 4.0},
    )


def _assessment(student_id: int, scores: dict[str, float]) -> RubricAssessment:
    return RubricAssessment(
        student_id=student_id,
        submission_id=student_id,
        criteria=tuple(
            RubricCriterionScore(criterion_id=cid, points=points, comments="")
            for cid, points in scores.items()
        ),
    )


def test_pairs_human_and_proxy_points_per_criterion() -> None:
    submissions = [_submission("1", "student1@asu.edu", set(_ALL_TEST_NAMES))]
    gradebook = CanvasGradebook(columns=(), rows=(_gradebook_row(1, "student1"),))
    assessments = [_assessment(1, {"c1": 1.0, "c2": 2.0})]

    result = compute_heat_map_rows(submissions, gradebook, _RUBRIC, assessments, _MAPPING)

    assert result.unmatched_submissions == ()
    assert result.failed_submissions == ()
    assert result.students_without_human_scores == ()
    assert set(result.rows) == {
        HeatMapScoreRow("student1", "main menu", human_points=1.0, proxy_points=2.0),
        HeatMapScoreRow("student1", "memory leaks", human_points=2.0, proxy_points=2.0),
    }


def test_submission_with_no_gradebook_row_is_unmatched() -> None:
    submissions = [_submission("1", "nobody@asu.edu", set(_ALL_TEST_NAMES))]
    gradebook = CanvasGradebook(columns=(), rows=())

    result = compute_heat_map_rows(submissions, gradebook, _RUBRIC, [], _MAPPING)

    assert result.unmatched_submissions == ("1",)
    assert result.rows == ()


def test_matched_student_with_no_rubric_assessment_is_listed() -> None:
    submissions = [_submission("1", "student1@asu.edu", set(_ALL_TEST_NAMES))]
    gradebook = CanvasGradebook(columns=(), rows=(_gradebook_row(1, "student1"),))

    result = compute_heat_map_rows(submissions, gradebook, _RUBRIC, [], _MAPPING)

    assert result.students_without_human_scores == ("student1",)
    assert result.rows == ()


def test_an_empty_submission_list_produces_an_empty_result() -> None:
    gradebook = CanvasGradebook(columns=(), rows=())

    result = compute_heat_map_rows([], gradebook, _RUBRIC, [], _MAPPING)

    assert result.rows == ()
    assert result.unmatched_submissions == ()
    assert result.failed_submissions == ()


def test_raises_when_a_mapping_criterion_has_no_matching_rubric_criterion() -> None:
    bad_mapping = ProxyGradeMapping(
        name="bad", criteria=(Criterion("not in rubric", (Tier(1.0, all_of=("Test X",)),)),)
    )

    with pytest.raises(Exception, match="not in rubric"):
        compute_heat_map_rows([], CanvasGradebook(columns=(), rows=()), _RUBRIC, [], bad_mapping)
