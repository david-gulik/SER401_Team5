"""Tests for LegacyGradebookCSVReader (infra/csv adapter)."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.infra.csv.canvas_gradebook_csv_reader import LegacyGradebookCSVReader

EXPECTED_STUDENT_COUNT = 3
EXPECTED_ASSIGNMENT_COUNT = 6


@pytest.fixture(scope="module")
def reader() -> LegacyGradebookCSVReader:
    return LegacyGradebookCSVReader()


@pytest.fixture(scope="module")
def gradebook(reader: LegacyGradebookCSVReader, gradebook_csv_path: Path):
    return reader.parse(gradebook_csv_path)


class TestGradebookStructure:
    def test_returns_canvas_gradebook(self, gradebook) -> None:
        assert type(gradebook).__name__ == "CanvasGradebook"

    def test_student_count_excludes_sentinel(self, gradebook) -> None:
        assert len(gradebook.rows) == EXPECTED_STUDENT_COUNT

    def test_assignment_column_count(self, gradebook) -> None:
        assert len(gradebook.columns) == EXPECTED_ASSIGNMENT_COUNT


class TestAssignmentColumns:
    def test_columns_are_assignment_columns(self, gradebook) -> None:
        assert all(type(c).__name__ == "GradebookAssignmentColumn" for c in gradebook.columns)

    def test_canvas_ids_are_extracted(self, gradebook) -> None:
        ids = {c.canvas_id for c in gradebook.columns}
        expected = {7216974, 7216976, 7216975, 7216973, 7216983, 7216972}
        assert ids == expected

    def test_display_name_strips_trailing_id(self, gradebook) -> None:
        col = next(c for c in gradebook.columns if c.canvas_id == 7216972)
        assert col.display_name == "Module 3: Programming (Gradescope)"

    def test_points_possible_parsed_as_float(self, gradebook) -> None:
        col = next(c for c in gradebook.columns if c.canvas_id == 7216974)
        assert col.points_possible == 10.0

    def test_points_possible_varies_across_columns(self, gradebook) -> None:
        points = {c.canvas_id: c.points_possible for c in gradebook.columns}
        assert points[7216975] == 5.0
        assert points[7216973] == 3.0
        assert points[7216983] == 30.0
        assert points[7216972] == 26.0


class TestStudentRows:
    def test_rows_are_student_rows(self, gradebook) -> None:
        assert all(type(r).__name__ == "GradebookStudentRow" for r in gradebook.rows)

    def test_student_name_mapped(self, gradebook) -> None:
        first = gradebook.rows[0]
        assert first.student_name == "Bourque, Bailey"

    def test_canvas_id_parsed_as_int(self, gradebook) -> None:
        assert all(isinstance(r.canvas_id, int) for r in gradebook.rows)
        assert gradebook.rows[0].canvas_id == 309780

    def test_sis_login_id_mapped(self, gradebook) -> None:
        assert gradebook.rows[0].sis_login_id == "brbourqu"

    def test_section_mapped(self, gradebook) -> None:
        assert all(r.section == "TRN-2026Spring-IVECapstone" for r in gradebook.rows)

    def test_sentinel_student_excluded(self, gradebook) -> None:
        names = [r.student_name for r in gradebook.rows]
        assert "Student, Test" not in names


class TestScoreParsing:
    def test_numeric_score_parsed_as_float(self, gradebook) -> None:
        bourque = gradebook.rows[0]
        header = next(c.raw_header for c in gradebook.columns if c.canvas_id == 7216974)
        assert bourque.assignment_scores[header] == 8.45

    def test_blank_score_parsed_as_none(self, gradebook) -> None:
        bourque = gradebook.rows[0]
        header = next(c.raw_header for c in gradebook.columns if c.canvas_id == 7216983)
        assert bourque.assignment_scores[header] is None

    def test_all_blank_scores_for_inactive_student(self, gradebook) -> None:
        crain = next(r for r in gradebook.rows if r.sis_login_id == "lcrain")
        assert all(v is None for v in crain.assignment_scores.values())

    def test_score_keys_match_column_headers(self, gradebook) -> None:
        expected_headers = {c.raw_header for c in gradebook.columns}
        for row in gradebook.rows:
            assert set(row.assignment_scores.keys()) == expected_headers
