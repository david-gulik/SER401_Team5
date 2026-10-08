from __future__ import annotations

from datetime import UTC, datetime

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook, GradebookStudentRow
from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier
from GAVEL.app.usecases.proxy_grade.generate_signed_error_report import compute_signed_error_rows

# A small mapping used only by these tests. Full marks are 5.0.
_MAPPING = ProxyGradeMapping(
    name="toy",
    criteria=(
        Criterion("first", (Tier(2.0, all_of=("Test A", "Test B")),)),
        Criterion("second", (Tier(3.0, all_of=("Test C",)),)),
    ),
)
_ALL_TEST_NAMES = list(_MAPPING.test_names())
_GRADEBOOK_COLUMN = "Module 2: Programming (123456)"


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


def _gradebook(rows: list[GradebookStudentRow]) -> CanvasGradebook:
    return CanvasGradebook(columns=(), rows=tuple(rows))


def test_works_directly_on_already_loaded_submissions_and_a_gradebook() -> None:
    submissions = [_submission("1", "student1@asu.edu", set(_ALL_TEST_NAMES))]
    gradebook = _gradebook(
        [
            GradebookStudentRow(
                student_name="One, Student",
                canvas_id=1,
                sis_login_id="student1",
                section="001",
                assignment_scores={_GRADEBOOK_COLUMN: 4.0},
            )
        ]
    )

    result = compute_signed_error_rows(submissions, gradebook, _GRADEBOOK_COLUMN, _MAPPING)

    assert result.unmatched_submissions == ()
    assert len(result.rows) == 1
    assert result.rows[0].proxy_score == 5.0
    assert result.rows[0].signed_error == -1.0


def test_an_empty_submission_list_produces_an_empty_result() -> None:
    gradebook = _gradebook([])

    result = compute_signed_error_rows([], gradebook, _GRADEBOOK_COLUMN, _MAPPING)

    assert result.rows == ()
    assert result.unmatched_submissions == ()
    assert result.failed_submissions == ()
