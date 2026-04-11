from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GradescopeSubmitter:
    sid: str
    email: str
    name: str


@dataclass(frozen=True)
class GradescopeTestScore:
    name: str
    score: float
    max_score: float | None = None
    number: str | None = None


@dataclass(frozen=True)
class GradescopeSubmission:
    submission_key: str
    submitter: GradescopeSubmitter
    created_at: datetime
    tests: list[GradescopeTestScore]
