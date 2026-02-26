"""Tests for CsvRosterReader (port layer)."""
from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.roster import RosterStudent
from GAVEL.app.ports.roster_reader import CsvRosterReader

EXPECTED_ROW_COUNT = 30


@pytest.fixture(scope="module")
def reader() -> CsvRosterReader:
    return CsvRosterReader()


@pytest.fixture(scope="module")
def students(
    reader: CsvRosterReader, roster_csv_path: Path
) -> list[RosterStudent]:
    return reader.read(roster_csv_path)


class TestCsvRosterReader:
    def test_returns_one_student_per_row(
        self, students: list[RosterStudent]
    ) -> None:
        assert len(students) == EXPECTED_ROW_COUNT

    def test_student_fields_are_mapped_correctly(
        self, students: list[RosterStudent]
    ) -> None:
        first = students[0]
        assert first.id == "1261966959"
        assert first.posting_id == "6959-899"
        assert first.first_name == "Kaori"
        assert first.last_name == "Fujii"
        assert first.status == "ENRL (2025-10-27)"
        assert first.grade_basis == "Standard"
        assert first.program_and_plan == (
            "Ira A Fulton Engineering - Software Engineering"
        )
        assert first.academic_level == "Senior"
        assert first.asurite == "kfujii"
        assert first.residency == "Resident"
        assert first.zoom_email == "kfujii@asu.edu"

    def test_units_is_parsed_as_int(
        self, students: list[RosterStudent]
    ) -> None:
        assert all(isinstance(s.units, int) for s in students)
        assert students[0].units == 3

    def test_returns_roster_student_instances(
        self, students: list[RosterStudent]
    ) -> None:
        assert all(isinstance(s, RosterStudent) for s in students)

    def test_mixed_residency_values_present(
        self, students: list[RosterStudent]
    ) -> None:
        residencies = {s.residency for s in students}
        assert residencies == {"Resident", "Non-Resident"}

    def test_mixed_academic_levels_present(
        self, students: list[RosterStudent]
    ) -> None:
        levels = {s.academic_level for s in students}
        expected = {"Sophomore", "Junior", "Senior", "Graduate"}
        assert levels >= expected
