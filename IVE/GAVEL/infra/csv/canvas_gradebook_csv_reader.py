from __future__ import annotations

import csv
import re
from pathlib import Path

from GAVEL.app.dtos.canvas_gradebook import (
    CanvasGradebook,
    GradebookAssignmentColumn,
    GradebookStudentRow,
)

# Canvas export preamble row indices (0-based after the header row is consumed
# by DictReader, so these are the first two next() calls on the reader).
_PREAMBLE_POSTING_ROW = 0   # "Manual Posting" flags row
_PREAMBLE_POINTS_ROW = 1    # "Points Possible" row

_SENTINEL_STUDENT = "Student, Test"
_READ_ONLY_MARKER = "(read only)"

# Matches the trailing Canvas assignment ID in parentheses, e.g. "(7216974)".
# Excludes aggregate column IDs since those never appear in an assignment header.
_ASSIGNMENT_ID_RE = re.compile(r"\((\d+)\)\s*$")


def _is_assignment_column(header: str) -> bool:
    """
    Returns True if this column header represents a student assignment.

    Assignment columns contain a colon separator (e.g. "Module 3: Programming")
    and end with a Canvas assignment ID in parentheses. Aggregate/read-only
    columns (e.g. "Activities Current Points") do not match this pattern.
    """
    return ":" in header and bool(_ASSIGNMENT_ID_RE.search(header))


def _parse_assignment_column(
    header: str, points_raw: str
) -> GradebookAssignmentColumn:
    """Extract metadata from an assignment column header and its points cell."""
    match = _ASSIGNMENT_ID_RE.search(header)
    canvas_id = int(match.group(1))
    display_name = header[: match.start()].strip()

    points: float | None = None
    if points_raw and points_raw != _READ_ONLY_MARKER:
        try:
            points = float(points_raw)
        except ValueError:
            pass

    return GradebookAssignmentColumn(
        raw_header=header,
        canvas_id=canvas_id,
        display_name=display_name,
        points_possible=points,
    )


def _parse_score(raw: str) -> float | None:
    """Convert a raw CSV score cell to float, or None if blank."""
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


class LegacyGradebookCSVReader:
    """
    Parses a Canvas gradebook CSV export from a local file path.

    This reader handles the 3-row preamble format emitted by Canvas exports:
      Row 1 (header): column names consumed by csv.DictReader
      Row 2: "Manual Posting" flags - consumed and discarded
      Row 3: "Points Possible" values - consumed to populate column metadata
      Row 4+: student data rows

    Only assignment columns (identified by colon separator + trailing Canvas ID)
    are retained. Aggregate/read-only columns are ignored. The "Student, Test"
    sentinel row is always excluded.

    """

    def parse(self, path: Path) -> CanvasGradebook:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)

            # Discard the "Manual Posting" preamble row.
            next(reader)

            # Consume the "Points Possible" row to extract column point values.
            points_row = next(reader)

            assignment_headers = [
                h for h in reader.fieldnames or []
                if _is_assignment_column(h)
            ]

            columns = tuple(
                _parse_assignment_column(h, points_row.get(h, ""))
                for h in assignment_headers
            )

            rows = tuple(
                self._parse_student_row(row, assignment_headers)
                for row in reader
                if not row["Student"].strip().startswith(_SENTINEL_STUDENT)
                and row["ID"].strip()  # skip blank/staff rows with no Canvas ID
            )

        return CanvasGradebook(columns=columns, rows=rows)

    def _parse_student_row(
        self,
        row: dict[str, str],
        assignment_headers: list[str],
    ) -> GradebookStudentRow:
        scores = {h: _parse_score(row.get(h, "")) for h in assignment_headers}
        return GradebookStudentRow(
            student_name=row["Student"].strip(),
            canvas_id=int(row["ID"].strip()),
            sis_login_id=row["SIS Login ID"].strip(),
            section=row["Section"].strip(),
            assignment_scores=scores,
        )
