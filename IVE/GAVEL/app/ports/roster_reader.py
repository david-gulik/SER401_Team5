from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

import pandas as pd

from GAVEL.app.dtos.roster import RosterStudent

# Maps CSV header names to RosterStudent field names.
_COLUMN_MAP: dict[str, str] = {
    "ID": "id",
    "Posting ID": "posting_id",
    "First Name": "first_name",
    "Last Name": "last_name",
    "Status": "status",
    "Units": "units",
    "Grade Basis": "grade_basis",
    "Program and Plan": "program_and_plan",
    "Academic Level": "academic_level",
    "ASURITE": "asurite",
    "Residency": "residency",
    "Zoom Email": "zoom_email",
}


class RosterReader(ABC):
    @abstractmethod
    def read(self, path: Path) -> List[RosterStudent]:
        """Load a roster file and return one RosterStudent per row."""
        raise NotImplementedError


class CsvRosterReader(RosterReader):
    """Reads the MyASU/PeopleSoft ground-truth roster CSV format."""

    def read(self, path: Path) -> List[RosterStudent]:
        df = pd.read_csv(path, dtype=str)
        df = df.rename(columns=_COLUMN_MAP)
        df["units"] = df["units"].astype(int)
        return [RosterStudent(**row) for row in df.to_dict(orient="records")]
