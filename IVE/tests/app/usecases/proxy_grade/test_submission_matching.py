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
    match_submission_to_gradebook_row,
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


def test_matches_a_submission_to_its_gradebook_row_by_login() -> None:
    submission = _submission("student1@asu.edu")
    row = GradebookStudentRow(
        student_name="One, Student",
        canvas_id=1,
        sis_login_id="student1",
        section="001",
        assignment_scores={},
    )
    gradebook = CanvasGradebook(columns=(), rows=(row,))

    assert match_submission_to_gradebook_row(submission, gradebook) is row


def test_no_match_when_no_row_has_that_login() -> None:
    submission = _submission("nobody@asu.edu")
    gradebook = CanvasGradebook(columns=(), rows=())

    assert match_submission_to_gradebook_row(submission, gradebook) is None


def test_no_tests_ran_is_true_when_every_test_is_missing_and_not_an_autograder_crash() -> None:
    submission = _submission("student1@asu.edu", output="Compilation failed.")
    try:
        compute_proxy_grade(submission, _MAPPING)
        raise AssertionError("expected MissingTestResultsError")
    except MissingTestResultsError as exc:
        assert no_tests_ran_on_the_submitted_code(submission, exc, _MAPPING)


def test_no_tests_ran_is_false_on_an_autograder_crash_message() -> None:
    submission = _submission(
        "student1@asu.edu", output="The autograder failed to execute correctly."
    )
    try:
        compute_proxy_grade(submission, _MAPPING)
        raise AssertionError("expected MissingTestResultsError")
    except MissingTestResultsError as exc:
        assert not no_tests_ran_on_the_submitted_code(submission, exc, _MAPPING)


def test_no_tests_ran_is_false_when_only_some_tests_are_missing() -> None:
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
    except MissingTestResultsError as exc:
        assert not no_tests_ran_on_the_submitted_code(submission, exc, mapping)
