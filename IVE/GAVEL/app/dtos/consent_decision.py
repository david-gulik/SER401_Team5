from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConsentStatus(Enum):
    """Outcome of consent filtering for one student.

    Every status except INCLUDED is a reason the student is left out of the
    anonymized dataset.
    """

    INCLUDED = "included"
    # latest attempt answered no to the consent question
    DECLINED = "declined"
    # consented but left the name question blank
    NAME_BLANK = "name_blank"
    # consented and the typed name is a letter or two away from the Canvas
    # name; left out until someone confirms it is the same student
    POSSIBLE_TYPO = "possible_typo"
    # consented but the typed name does not match the Canvas name
    NAME_MISMATCH = "name_mismatch"
    # on the roster but never submitted the consent form
    NO_RESPONSE = "no_response"


@dataclass(frozen=True)
class ConsentDecision:
    """Whether one student was kept by consent filtering, and why.

    Consent fields come from the student's latest attempt. A NO_RESPONSE
    student has no attempt, so canvas_id, attempt, name_response and
    consented are None.
    """

    sis_id: int
    name: str
    status: ConsentStatus
    canvas_id: int | None = None
    attempt: int | None = None
    name_response: str | None = None
    consented: bool | None = None

    @property
    def included(self) -> bool:
        return self.status is ConsentStatus.INCLUDED
