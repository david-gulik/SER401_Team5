from __future__ import annotations

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.usecases.compute_r_squared import compute_r_squared


def compute_cross_assessment_correlation(
    gradebook: CanvasGradebook, column_a: str, column_b: str
) -> float:
    """r-squared between two gradebook columns (i.e. a programming assignment and a quiz).

    Students with a score in both columns are compared. Raises ValueError and names the column if either column is not in the
    gradebook. Also raises ValueError (from compute_r_squared) if fewer than
    two students have a score in both columns, or either column's scores,
    among those students, are all the same value.
    """
    valid_columns = {column.raw_header for column in gradebook.columns}
    for column in (column_a, column_b):
        if column not in valid_columns:
            raise ValueError(f"{column!r} is not a column in this gradebook.")

    paired_scores = [
        (row.assignment_scores[column_a], row.assignment_scores[column_b])
        for row in gradebook.rows
        if row.assignment_scores[column_a] is not None
        and row.assignment_scores[column_b] is not None
    ]

    return compute_r_squared(
        [score_a for score_a, _ in paired_scores],
        [score_b for _, score_b in paired_scores],
    )
