"""
Reads Gradescope submission YAML files and a Canvas gradebook CSV,
computes each submission's proxy score, and pairs it with that student's human
score to compute signed error (human minus proxy).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.proxy_grade_mapping import ProxyGradeMapping
from GAVEL.app.ports.gradescope_reader import GradescopeReader
from GAVEL.app.usecases.proxy_grade.compute_proxy_grade import (
    MissingTestResultsError,
    compute_proxy_grade,
)


class GradebookCSVReader(Protocol):
    """Structural type for the gradebook CSV reader dependency.

    LegacyGradebookCSVReader satisfies this without implementing the
    (currently unused) GradebookReader port, so tests can supply a fake
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
        human_scores_by_login = {
            row.sis_login_id.lower(): row.assignment_scores.get(request.gradebook_column)
            for row in gradebook.rows
        }

        rows: list[SubmissionSignedError] = []
        unmatched: list[str] = []
        failed: list[FailedSubmission] = []

        submission_paths = sorted(request.submissions_dir.glob("*.yml")) + sorted(
            request.submissions_dir.glob("*.yaml")
        )

        for yaml_path in submission_paths:
            for submission in self._gradescope_reader.read(yaml_path):
                login = _student_key(submission.submitter.email)
                human_score = human_scores_by_login.get(login)

                if human_score is None:
                    unmatched.append(submission.submitter.sid or submission.submission_key)
                    continue

                try:
                    proxy_result = compute_proxy_grade(submission, request.mapping)
                except MissingTestResultsError as exc:
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
                        proxy_score=proxy_result.total_score,
                        signed_error=human_score - proxy_result.total_score,
                    )
                )

        result = GenerateSignedErrorReportResult(
            rows=tuple(rows),
            unmatched_submissions=tuple(unmatched),
            failed_submissions=tuple(failed),
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
