from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from IVE.GAVEL.app.dtos.asu_roster import RosterStudent
from IVE.GAVEL.app.ports.asu_roster_reader import RosterReader

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


class CanvasRosterCSVReader(RosterReader):
    """Reads the MyASU/PeopleSoft ground-truth roster CSV format."""

    def read(self, path: Path) -> List[RosterStudent]:
        df = pd.read_csv(path, dtype=str)
        df = df.rename(columns=_COLUMN_MAP)
        df["units"] = df["units"].astype(int)
        return [RosterStudent(**row) for row in df.to_dict(orient="records")]
