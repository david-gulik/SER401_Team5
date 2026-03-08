from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GradebookAssignmentColumn:
    """
    Metadata for a single assignment column parsed from the gradebook header.

    Canvas encodes assignment columns as:
        "<Module>: <Name> (<optional section metadata>) (<canvas_assignment_id>)"

    The canvas_id is the trailing integer in parentheses. points_possible is
    populated from Row 3 of the export (the Points Possible preamble row).
    """
    raw_header: str        # original column name as it appears in the CSV
    canvas_id: int         # Canvas assignment ID extracted from trailing parens
    display_name: str      # header stripped of the trailing "(canvas_id)"
    points_possible: float | None


@dataclass(frozen=True)
class GradebookStudentRow:
    """
    One student data row from a Canvas gradebook CSV export.

    Identity fields reflect the confirmed column names from the exported sample.
    Note: the export uses "ID" (Canvas internal int) and "SIS Login ID" (ASURITE).

    assignment_scores maps raw_header -> float | None (None when cell is blank).
    Only assignment columns are included; aggregate/read-only columns are excluded.
    """
    student_name: str               # "Last, First" format
    canvas_id: int                  # Canvas internal student ID (column: "ID")
    sis_login_id: str               # ASURITE username (column: "SIS Login ID")
    section: str
    assignment_scores: dict[str, float | None]  # raw_header -> score


@dataclass(frozen=True)
class CanvasGradebook:
    """
    Full parsed representation of a Canvas gradebook CSV export.

    columns contains only assignment columns (excludes aggregate/read-only).
    rows excludes the "Student, Test" sentinel and any blank/staff rows.
    """
    columns: tuple[GradebookAssignmentColumn, ...]
    rows: tuple[GradebookStudentRow, ...]
