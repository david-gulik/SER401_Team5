from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConsentStatus(Enum):
    """Outcome of consent filtering for one student.

    INCLUDED and OVERRIDDEN keep the student in the anonymized dataset; every
    other status is a reason the student is left out.
    """

    INCLUDED = "included"
    # the typed name was a possible typo or a mismatch, and someone confirmed
    # by hand that it is the same student
    OVERRIDDEN = "overridden"
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


INCLUDED_STATUSES = frozenset({ConsentStatus.INCLUDED, ConsentStatus.OVERRIDDEN})

# Name problems close enough to the Canvas name that a person may confirm the
# student by hand. A blank name is too far off to confirm.
OVERRIDABLE_STATUSES = frozenset({ConsentStatus.POSSIBLE_TYPO, ConsentStatus.NAME_MISMATCH})


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
        return self.status in INCLUDED_STATUSES

    @property
    def overridable(self) -> bool:
        return self.status in OVERRIDABLE_STATUSES
