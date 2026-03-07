from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class GradescopeSubmitter:
    sid: str
    email: str
    name: str


@dataclass(frozen=True)
class GradescopeTestScore:
    name: str
    score: float
    max_score: Optional[float] = None
    number: Optional[str] = None


@dataclass(frozen=True)
class GradescopeSubmission:
    submission_key: str
    submitter: GradescopeSubmitter
    created_at: datetime
    tests: List[GradescopeTestScore]
