from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from GAVEL.app.dtos.roster import RosterStudent


class RosterReader(ABC):
    @abstractmethod
    def read(self, path: Path) -> List[RosterStudent]:
        """Load a roster file and return one RosterStudent per row."""
        raise NotImplementedError
