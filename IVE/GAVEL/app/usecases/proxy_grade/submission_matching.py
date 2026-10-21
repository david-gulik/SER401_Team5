"""Matches a Gradescope submission to the Canvas identity that graded it.

Shared by every report that pairs a submission's proxy score with a human
score, regardless of where that human score comes from (a gradebook column,
a rubric assessment, ...).
"""

from __future__ import annotations

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook, GradebookStudentRow
from GAVEL.app.dtos.gradescope import GradescopeSubmission

# Gradescope message when the autograder process itself crashes or times
# out, distinct from a message an assignment's own autograder writes about
# the submission it was given. Used to tell those apart when every test the
# mapping refers to is missing from a submission's results.
_AUTOGRADER_CRASHED_MESSAGE = "The autograder failed to execute correctly."


def student_key(email: str) -> str:
    """The email's local part (before @), lowercased.

    Used to match a Gradescope submitter to a gradebook row by SIS login ID,
    assuming the SIS login ID equals the email's local part. Check for an
    unmatched submission before trusting the result.
    """
    return email.split("@")[0].strip().lower()


def match_submission_to_gradebook_row(
    submission: GradescopeSubmission, gradebook: CanvasGradebook
) -> GradebookStudentRow | None:
    """The gradebook row for a submission's submitter, by SIS login ID.

    Public so any caller matching a submission to a student's Canvas
    identity, not only a signed-error report, uses the same matching rule.
    """
    login = student_key(submission.submitter.email)
    return next((row for row in gradebook.rows if row.sis_login_id.lower() == login), None)


def no_tests_ran_on_the_submitted_code(submission: GradescopeSubmission) -> bool:
    """A submission scores 0 rather than being reported as failed when it has no
    test results at all and the autograder's own output explains why, as opposed
    to Gradescope's generic message for when the autograder process itself
    crashed or timed out.

    A submission that has test results but none matching the mapping, for
    example after a test rename or when a mapping is applied to the wrong
    assignment, is reported as failed instead of scored zero, since scoring it
    zero would hide the mismatch.
    """
    if submission.tests:
        return False
    if not submission.output:
        return False
    return _AUTOGRADER_CRASHED_MESSAGE not in submission.output
