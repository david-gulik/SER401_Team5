from __future__ import annotations

from datetime import UTC, datetime

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook, GradebookStudentRow
from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier
from GAVEL.app.usecases.proxy_grade.compute_proxy_grade import (
    MissingTestResultsError,
    compute_proxy_grade,
)
from GAVEL.app.usecases.proxy_grade.submission_matching import (
    gradebook_rows_by_login,
    no_tests_ran_on_the_submitted_code,
    student_key,
)

_MAPPING = ProxyGradeMapping(
    name="toy", criteria=(Criterion("only", (Tier(2.0, all_of=("Test A",)),)),)
)


def _submission(email: str, output: str | None = None, tests: list | None = None):
    return GradescopeSubmission(
        submission_key="submission_1",
        submitter=GradescopeSubmitter(sid="1", email=email, name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests or [],
        output=output,
    )


def test_student_key_takes_the_email_local_part_lowercased() -> None:
    assert student_key("Student1@ASU.edu") == "student1"


def test_gradebook_rows_by_login_keys_each_row_by_its_lowercased_login() -> None:
    row = GradebookStudentRow(
        student_name="One, Student",
        canvas_id=1,
        sis_login_id="Student1",
        section="001",
        assignment_scores={},
    )
    gradebook = CanvasGradebook(columns=(), rows=(row,))

    assert gradebook_rows_by_login(gradebook) == {"student1": row}


def test_gradebook_rows_by_login_is_empty_for_an_empty_gradebook() -> None:
    gradebook = CanvasGradebook(columns=(), rows=())

    assert gradebook_rows_by_login(gradebook) == {}


def test_no_tests_ran_is_true_when_every_test_is_missing_and_not_an_autograder_crash() -> None:
    submission = _submission("student1@asu.edu", output="Compilation failed.")
    try:
        compute_proxy_grade(submission, _MAPPING)
        raise AssertionError("expected MissingTestResultsError")
    except MissingTestResultsError:
        assert no_tests_ran_on_the_submitted_code(submission)


def test_no_tests_ran_is_false_on_an_autograder_crash_message() -> None:
    submission = _submission(
        "student1@asu.edu", output="The autograder failed to execute correctly."
    )
    try:
        compute_proxy_grade(submission, _MAPPING)
        raise AssertionError("expected MissingTestResultsError")
    except MissingTestResultsError:
        assert not no_tests_ran_on_the_submitted_code(submission)


def test_no_tests_ran_is_false_when_the_submission_has_unmatched_test_results() -> None:
    mapping = ProxyGradeMapping(
        name="two",
        criteria=(
            Criterion("first", (Tier(2.0, all_of=("Test A",)),)),
            Criterion("second", (Tier(2.0, all_of=("Test B",)),)),
        ),
    )
    submission = _submission(
        "student1@asu.edu",
        output="Compilation failed.",
        tests=[GradescopeTestScore(name="Test A", score=1.0, max_score=1.0)],
    )
    try:
        compute_proxy_grade(submission, mapping)
        raise AssertionError("expected MissingTestResultsError")
    except MissingTestResultsError:
        assert not no_tests_ran_on_the_submitted_code(submission)
