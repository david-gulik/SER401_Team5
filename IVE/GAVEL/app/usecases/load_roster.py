from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from GAVEL.app.ports.roster_reader import RosterReader


@dataclass(frozen=True)
class LoadRosterRequest:
    path: Path


class LoadRosterUseCase:
    def __init__(self, reader: RosterReader) -> None:
        self._reader = reader

    def execute(self, request: LoadRosterRequest) -> pd.DataFrame:
        """Return a pandas DataFrame with one row per enrolled student."""
        students = self._reader.read(request.path)
        return pd.DataFrame([dataclasses.asdict(s) for s in students])
