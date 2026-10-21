"""Reads Gradescope submissions, a gradebook, and a rubric's human assessments,
scores each submission's per-criterion proxy points, and pairs them with the
same student's per-criterion human points for the heat map.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.gradescope import GradescopeSubmission
from GAVEL.app.dtos.proxy_grade_mapping import ProxyGradeMapping
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.app.usecases.build_per_criterion_human_scores import build_per_criterion_human_scores
from GAVEL.app.usecases.match_proxy_criteria_to_rubric import match_proxy_criteria_to_rubric
from GAVEL.app.usecases.proxy_grade.compute_proxy_grade import (
    MissingTestResultsError,
    compute_proxy_grade,
)
from GAVEL.app.usecases.proxy_grade.submission_matching import (
    match_submission_to_gradebook_row,
    no_tests_ran_on_the_submitted_code,
    student_key,
)


@dataclass(frozen=True)
class HeatMapScoreRow:
    student_identifier: str
    criterion: str
    human_points: float
    proxy_points: float


@dataclass(frozen=True)
class FailedSubmission:
    submission_id: str
    missing_tests: tuple[str, ...]


@dataclass(frozen=True)
class GenerateHeatMapReportResult:
    rows: tuple[HeatMapScoreRow, ...]
    unmatched_submissions: tuple[str, ...]
    failed_submissions: tuple[FailedSubmission, ...] = ()
    # Matched a gradebook row, but that student has no rubric assessment for
    # this assignment at all (declined consent, never graded, ...).
    students_without_human_scores: tuple[str, ...] = ()


def compute_heat_map_rows(
    submissions: Sequence[GradescopeSubmission],
    gradebook: CanvasGradebook,
    rubric_definition: RubricDefinition,
    rubric_assessments: Sequence[RubricAssessment],
    mapping: ProxyGradeMapping,
) -> GenerateHeatMapReportResult:
    """Matches submissions to a gradebook and a rubric, scoring each criterion.

    Works entirely on already-loaded data, mirroring compute_signed_error_rows.
    Raises UnmatchedProxyCriterionError if the mapping's criteria do not match
    the rubric's, and UnknownRubricCriterionError if an assessment refers to a
    criterion the rubric definition does not have: both are whole-report
    preconditions, not a single submission's problem.
    """
    criterion_match = match_proxy_criteria_to_rubric(mapping, rubric_definition)
    human_scores = build_per_criterion_human_scores(rubric_definition, rubric_assessments)
    human_points_by_student_and_criterion = {
        (score.student_id, score.criterion): score.points for score in human_scores
    }

    rows: list[HeatMapScoreRow] = []
    unmatched: list[str] = []
    failed: list[FailedSubmission] = []
    missing_human: list[str] = []

    for submission in submissions:
        login = student_key(submission.submitter.email)
        row = match_submission_to_gradebook_row(submission, gradebook)
        if row is None:
            unmatched.append(submission.submitter.sid or submission.submission_key)
            continue

        try:
            proxy_result = compute_proxy_grade(submission, mapping)
            criterion_scores = proxy_result.criterion_scores
        except MissingTestResultsError as exc:
            if no_tests_ran_on_the_submitted_code(submission):
                criterion_scores = tuple(0.0 for _ in mapping.criteria)
            else:
                failed.append(
                    FailedSubmission(
                        submission_id=submission.submitter.sid or submission.submission_key,
                        missing_tests=exc.missing,
                    )
                )
                continue

        found_any = False
        for criterion, proxy_points in zip(mapping.criteria, criterion_scores, strict=True):
            rubric_criterion = criterion_match[criterion.name]
            human_points = human_points_by_student_and_criterion.get(
                (row.canvas_id, rubric_criterion.description)
            )
            if human_points is None:
                continue
            rows.append(
                HeatMapScoreRow(
                    student_identifier=login,
                    criterion=criterion.name,
                    human_points=human_points,
                    proxy_points=proxy_points,
                )
            )
            found_any = True

        if not found_any:
            missing_human.append(login)

    return GenerateHeatMapReportResult(
        rows=tuple(rows),
        unmatched_submissions=tuple(unmatched),
        failed_submissions=tuple(failed),
        students_without_human_scores=tuple(missing_human),
    )


def write_heat_map_report(result: GenerateHeatMapReportResult, output_path: Path) -> None:
    """Writes a result to disk in the heat map report's JSON format.

    Public so any caller with a GenerateHeatMapReportResult, not only a
    report-generating use case, writes the same file shape.
    """
    payload = {
        "rows": [
            {
                "student_identifier": row.student_identifier,
                "criterion": row.criterion,
                "human_points": row.human_points,
                "proxy_points": row.proxy_points,
            }
            for row in result.rows
        ],
        "unmatched_submissions": list(result.unmatched_submissions),
        "failed_submissions": [
            {"submission_id": f.submission_id, "missing_tests": list(f.missing_tests)}
            for f in result.failed_submissions
        ],
        "students_without_human_scores": list(result.students_without_human_scores),
    }
    output_path.write_text(json.dumps(payload, indent=2))
