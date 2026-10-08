"""
Reads Gradescope submission YAML files and a Canvas gradebook CSV,
computes each submission's proxy score, and pairs it with that student's human
score to compute signed error (human minus proxy).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.gradescope import GradescopeSubmission
from GAVEL.app.dtos.proxy_grade_mapping import ProxyGradeMapping
from GAVEL.app.ports.gradescope_reader import GradescopeReader
from GAVEL.app.usecases.proxy_grade.compute_proxy_grade import (
    MissingTestResultsError,
    compute_proxy_grade,
)

# Gradescope message when the autograder process itself crashes or
# times out, distinct from a message an assignment's own autograder writes
# about the submission it was given. Used to tell those apart when every
# test the mapping refers to is missing from a submission's results.
_AUTOGRADER_CRASHED_MESSAGE = "The autograder failed to execute correctly."


class GradebookCSVReader(Protocol):
    """Structural type for the gradebook CSV reader dependency.

    LegacyGradebookCSVReader satisfies this without implementing the
    (currently unused) GradebookReader port so that tests can supply a fake
    without subclassing a concrete class.
    """

    def parse(self, path: Path) -> CanvasGradebook: ...


@dataclass(frozen=True)
class SubmissionSignedError:
    student_identifier: str
    human_score: float
    proxy_score: float
    signed_error: float


@dataclass(frozen=True)
class FailedSubmission:
    submission_id: str
    missing_tests: tuple[str, ...]


@dataclass(frozen=True)
class GenerateSignedErrorReportRequest:
    submissions_dir: Path
    mapping: ProxyGradeMapping
    gradebook_path: Path
    gradebook_column: str
    output_path: Path


@dataclass(frozen=True)
class GenerateSignedErrorReportResult:
    rows: tuple[SubmissionSignedError, ...]
    unmatched_submissions: tuple[str, ...]
    failed_submissions: tuple[FailedSubmission, ...] = ()


def _student_key(email: str) -> str:
    """The email's local part (before @), lowercased.

    Used to match a Gradescope submitter to a gradebook row by SIS login ID,
    assuming the SIS login ID equals the email's local part. Check
    unmatched_submissions on the result before trusting the output.
    """
    return email.split("@")[0].strip().lower()


def _no_tests_ran_on_the_submitted_code(
    submission: GradescopeSubmission, exc: MissingTestResultsError, mapping: ProxyGradeMapping
) -> bool:
    """A submission scores 0 rather than being excluded when every test that the
    mapping refers to is missing and the autograder's own output explains why,
    as opposed to Gradescope's generic message for when the autograder process
    itself crashed or timed out.
    """
    if len(exc.missing) != len(mapping.test_names()):
        return False
    if not submission.output:
        return False
    return _AUTOGRADER_CRASHED_MESSAGE not in submission.output


def compute_signed_error_rows(
    submissions: Sequence[GradescopeSubmission],
    gradebook: CanvasGradebook,
    gradebook_column: str,
    mapping: ProxyGradeMapping,
) -> GenerateSignedErrorReportResult:
    """Matches submissions to a gradebook and scores each one against a mapping.

    Works entirely on already-loaded data, so a caller that already has its
    submissions and gradebook in hand (rather than paths to read them from)
    can get the same rows, unmatched list, and failed list that the report
    use case writes to disk.
    """
    human_scores_by_login = {
        row.sis_login_id.lower(): row.assignment_scores.get(gradebook_column)
        for row in gradebook.rows
    }

    rows: list[SubmissionSignedError] = []
    unmatched: list[str] = []
    failed: list[FailedSubmission] = []

    for submission in submissions:
        login = _student_key(submission.submitter.email)
        human_score = human_scores_by_login.get(login)

        if human_score is None:
            unmatched.append(submission.submitter.sid or submission.submission_key)
            continue

        try:
            proxy_result = compute_proxy_grade(submission, mapping)
            proxy_score = proxy_result.total_score
        except MissingTestResultsError as exc:
            if _no_tests_ran_on_the_submitted_code(submission, exc, mapping):
                proxy_score = 0.0
            else:
                failed.append(
                    FailedSubmission(
                        submission_id=submission.submitter.sid or submission.submission_key,
                        missing_tests=exc.missing,
                    )
                )
                continue

        rows.append(
            SubmissionSignedError(
                student_identifier=login,
                human_score=human_score,
                proxy_score=proxy_score,
                signed_error=human_score - proxy_score,
            )
        )

    return GenerateSignedErrorReportResult(
        rows=tuple(rows),
        unmatched_submissions=tuple(unmatched),
        failed_submissions=tuple(failed),
    )


class GenerateSignedErrorReportUseCase:
    def __init__(
        self,
        gradescope_reader: GradescopeReader,
        gradebook_reader: GradebookCSVReader,
    ) -> None:
        self._gradescope_reader = gradescope_reader
        self._gradebook_reader = gradebook_reader

    def execute(self, request: GenerateSignedErrorReportRequest) -> GenerateSignedErrorReportResult:
        gradebook = self._gradebook_reader.parse(request.gradebook_path)

        submission_paths = sorted(request.submissions_dir.glob("*.yml")) + sorted(
            request.submissions_dir.glob("*.yaml")
        )
        submissions = [
            submission
            for yaml_path in submission_paths
            for submission in self._gradescope_reader.read(yaml_path)
        ]

        result = compute_signed_error_rows(
            submissions, gradebook, request.gradebook_column, request.mapping
        )
        _write_report(result, request.output_path)
        return result


def _write_report(result: GenerateSignedErrorReportResult, output_path: Path) -> None:
    payload = {
        "rows": [
            {
                "student_identifier": row.student_identifier,
                "human_score": row.human_score,
                "proxy_score": row.proxy_score,
                "signed_error": row.signed_error,
            }
            for row in result.rows
        ],
        "unmatched_submissions": list(result.unmatched_submissions),
        "failed_submissions": [
            {"submission_id": f.submission_id, "missing_tests": list(f.missing_tests)}
            for f in result.failed_submissions
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2))
