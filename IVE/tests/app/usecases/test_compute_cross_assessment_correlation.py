from __future__ import annotations

import pytest

from GAVEL.app.dtos.canvas_gradebook import (
    CanvasGradebook,
    GradebookAssignmentColumn,
    GradebookStudentRow,
)
from GAVEL.app.usecases.compute_cross_assessment_correlation import (
    compute_cross_assessment_correlation,
)

_PROGRAMMING = "M2: Programming (111)"
_QUIZ = "Quiz 3 (222)"


def _column(raw_header: str) -> GradebookAssignmentColumn:
    return GradebookAssignmentColumn(
        raw_header=raw_header, canvas_id=1, display_name=raw_header, points_possible=10.0
    )


def _row(canvas_id: int, programming: float | None, quiz: float | None) -> GradebookStudentRow:
    return GradebookStudentRow(
        student_name=f"Student {canvas_id}",
        canvas_id=canvas_id,
        sis_login_id=f"student{canvas_id}",
        section="001",
        assignment_scores={_PROGRAMMING: programming, _QUIZ: quiz},
    )


def _gradebook(rows: list[GradebookStudentRow]) -> CanvasGradebook:
    return CanvasGradebook(columns=(_column(_PROGRAMMING), _column(_QUIZ)), rows=tuple(rows))


def test_an_unknown_column_is_rejected() -> None:
    gradebook = _gradebook([_row(1, 5.0, 5.0)])

    with pytest.raises(ValueError, match="Nonexistent Column"):
        compute_cross_assessment_correlation(gradebook, "Nonexistent Column", _QUIZ)


def test_a_student_missing_either_score_is_excluded() -> None:
    gradebook = _gradebook(
        [
            _row(1, 2.0, 4.0),
            _row(2, 4.0, 8.0),
            _row(3, None, 9.0),  # excluded: no programming score
            _row(4, 6.0, None),  # excluded: no quiz score
            _row(5, 6.0, 12.0),
        ]
    )

    # Only rows 1, 2, 5 remain, and quiz = 2 * programming for all three.
    assert compute_cross_assessment_correlation(gradebook, _PROGRAMMING, _QUIZ) == pytest.approx(
        1.0
    )


def test_comparing_a_column_to_itself_is_a_perfect_match() -> None:
    gradebook = _gradebook([_row(1, 2.0, 9.0), _row(2, 5.0, 1.0), _row(3, 8.0, 3.0)])

    assert compute_cross_assessment_correlation(
        gradebook, _PROGRAMMING, _PROGRAMMING
    ) == pytest.approx(1.0)


def test_fewer_than_two_matched_students_is_rejected() -> None:
    gradebook = _gradebook([_row(1, 5.0, 5.0), _row(2, None, 9.0)])

    with pytest.raises(ValueError):
        compute_cross_assessment_correlation(gradebook, _PROGRAMMING, _QUIZ)
