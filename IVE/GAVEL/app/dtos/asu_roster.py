from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RosterStudent:
    id: str
    posting_id: str
    first_name: str
    last_name: str
    status: str
    units: int
    grade_basis: str
    program_and_plan: str
    academic_level: str
    asurite: str
    residency: str
    zoom_email: str
