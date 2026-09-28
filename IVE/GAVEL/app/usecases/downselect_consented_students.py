from __future__ import annotations

import re
from dataclasses import dataclass

from GAVEL.app.dtos.asu_roster import RosterStudent
from GAVEL.app.dtos.canvas_consent_form_entry import ConsentFormEntry
from GAVEL.app.dtos.consent_decision import ConsentDecision, ConsentStatus


@dataclass(frozen=True)
class DownselectConsentedStudentsRequest:
    entries: tuple[ConsentFormEntry, ...]
    # Roster students with no consent form entry are reported as NO_RESPONSE.
    roster: tuple[RosterStudent, ...] = ()


@dataclass(frozen=True)
class DownselectConsentedStudentsResult:
    consented_ids: tuple[int, ...]
    included_count: int
    # Consent form respondents who were left out. NO_RESPONSE students are
    # not counted here because they never appear on the consent form.
    excluded_count: int
    # One decision per student, sorted by name.
    decisions: tuple[ConsentDecision, ...] = ()

    def count(self, status: ConsentStatus) -> int:
        return sum(1 for decision in self.decisions if decision.status is status)


class DownselectConsentedStudentsUseCase:
    def execute(
        self,
        request: DownselectConsentedStudentsRequest,
    ) -> DownselectConsentedStudentsResult:
        latest_by_student: dict[int, ConsentFormEntry] = {}

        for entry in request.entries:
            current = latest_by_student.get(entry.canvas_id)
            if current is None or entry.attempt > current.attempt:
                latest_by_student[entry.canvas_id] = entry

        decisions = [
            ConsentDecision(
                sis_id=entry.sis_id,
                name=entry.lms_name,
                status=_classify(entry),
                canvas_id=entry.canvas_id,
                attempt=entry.attempt,
                name_response=entry.name_response,
                consented=entry.consented,
            )
            for entry in latest_by_student.values()
        ]

        seen_sis_ids = {entry.sis_id for entry in latest_by_student.values()}

        for student in request.roster:
            sis_id = int(student.id)
            if sis_id in seen_sis_ids:
                continue
            seen_sis_ids.add(sis_id)
            decisions.append(
                ConsentDecision(
                    sis_id=sis_id,
                    name=f"{student.first_name} {student.last_name}",
                    status=ConsentStatus.NO_RESPONSE,
                )
            )

        decisions.sort(key=lambda decision: (decision.name.lower(), decision.sis_id))

        consented_ids = sorted(
            decision.canvas_id
            for decision in decisions
            if decision.included and decision.canvas_id is not None
        )
        excluded_count = sum(
            1
            for decision in decisions
            if not decision.included and decision.status is not ConsentStatus.NO_RESPONSE
        )

        return DownselectConsentedStudentsResult(
            consented_ids=tuple(consented_ids),
            included_count=len(consented_ids),
            excluded_count=excluded_count,
            decisions=tuple(decisions),
        )


def _classify(entry: ConsentFormEntry) -> ConsentStatus:
    if not entry.consented:
        return ConsentStatus.DECLINED

    lms_name = entry.lms_name.lower().strip()
    response = entry.name_response.lower().strip()

    if not response:
        return ConsentStatus.NAME_BLANK

    if response == lms_name:
        return ConsentStatus.INCLUDED

    # Any word of the Canvas name appearing in the response counts as a match,
    # so first and last names typed in either order are accepted.
    lms_chunks = [chunk for chunk in lms_name.split() if chunk]
    if any(chunk in response for chunk in lms_chunks):
        return ConsentStatus.INCLUDED

    if _has_near_match(lms_name, response):
        return ConsentStatus.POSSIBLE_TYPO

    return ConsentStatus.NAME_MISMATCH


def _name_words(name: str) -> list[str]:
    # Letters only, so commas and periods ("Bourque, B.") do not affect matching.
    return re.findall(r"[^\W\d_]+", name.lower())


def _allowed_typos(word: str) -> int:
    # Short names get no tolerance; one edit turns "Li" into "Lu" or "Bo" into "Jo".
    if len(word) < 4:
        return 0
    if len(word) < 8:
        return 1
    return 2


def _has_near_match(lms_name: str, response: str) -> bool:
    response_words = _name_words(response)

    for lms_word in _name_words(lms_name):
        allowed = _allowed_typos(lms_word)
        if allowed and any(
            _edit_distance(lms_word, response_word) <= allowed for response_word in response_words
        ):
            return True

    return False


def _edit_distance(a: str, b: str) -> int:
    """Number of single-letter insertions, deletions, substitutions, or swaps
    of two neighboring letters needed to turn a into b."""
    previous_row: list[int] | None = None
    row = list(range(len(b) + 1))

    for i in range(1, len(a) + 1):
        before_previous_row, previous_row = previous_row, row
        row = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            row[j] = min(
                previous_row[j] + 1,
                row[j - 1] + 1,
                previous_row[j - 1] + cost,
            )
            swapped = j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]
            if before_previous_row is not None and swapped:
                row[j] = min(row[j], before_previous_row[j - 2] + 1)

    return row[len(b)]
