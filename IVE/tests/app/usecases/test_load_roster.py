"""Tests for LoadRosterUseCase (use-case layer).

The RosterReader port is stubbed so this layer is tested in isolation.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd
import pytest

from GAVEL.app.dtos.roster import RosterStudent
from GAVEL.app.ports.roster_reader import RosterReader
from GAVEL.app.usecases.load_roster import LoadRosterRequest, LoadRosterUseCase


def _make_student(**overrides) -> RosterStudent:
    defaults = dict(
        id="1261966959",
        posting_id="6959-899",
        first_name="Kaori",
        last_name="Fujii",
        status="ENRL (2025-10-27)",
        units=3,
        grade_basis="Standard",
        program_and_plan="Ira A Fulton Engineering - Software Engineering",
        academic_level="Senior",
        asurite="kfujii",
        residency="Resident",
        zoom_email="kfujii@asu.edu",
    )
    return RosterStudent(**{**defaults, **overrides})


class StubRosterReader(RosterReader):
    """Returns a fixed list of students regardless of path."""

    def __init__(self, students: List[RosterStudent]) -> None:
        self._students = students

    def read(self, path: Path) -> List[RosterStudent]:
        return self._students


@pytest.fixture()
def two_students() -> List[RosterStudent]:
    return [
        _make_student(),
        _make_student(
            id="1240101287",
            posting_id="1287-157",
            first_name="Kana",
            last_name="Fujita",
            academic_level="Sophomore",
            asurite="kfujita",
            zoom_email="kfujita@asu.edu",
        ),
    ]


@pytest.fixture()
def use_case(two_students: List[RosterStudent]) -> LoadRosterUseCase:
    return LoadRosterUseCase(StubRosterReader(two_students))


class TestLoadRosterUseCase:
    def test_returns_dataframe(self, use_case: LoadRosterUseCase) -> None:
        df = use_case.execute(LoadRosterRequest(path=Path("irrelevant.csv")))
        assert isinstance(df, pd.DataFrame)

    def test_one_row_per_student(
        self,
        use_case: LoadRosterUseCase,
        two_students: List[RosterStudent],
    ) -> None:
        df = use_case.execute(LoadRosterRequest(path=Path("irrelevant.csv")))
        assert len(df) == len(two_students)

    def test_columns_match_dto_fields(
        self, use_case: LoadRosterUseCase
    ) -> None:
        df = use_case.execute(LoadRosterRequest(path=Path("irrelevant.csv")))
        expected_columns = {
            "id", "posting_id", "first_name", "last_name", "status",
            "units", "grade_basis", "program_and_plan", "academic_level",
            "asurite", "residency", "zoom_email",
        }
        assert set(df.columns) == expected_columns

    def test_cell_values_match_student_data(
        self, use_case: LoadRosterUseCase
    ) -> None:
        df = use_case.execute(LoadRosterRequest(path=Path("irrelevant.csv")))
        assert df.iloc[0]["first_name"] == "Kaori"
        assert df.iloc[1]["first_name"] == "Kana"
        assert df.iloc[0]["units"] == 3
