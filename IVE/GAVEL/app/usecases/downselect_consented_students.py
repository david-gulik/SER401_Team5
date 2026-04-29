from __future__ import annotations

from dataclasses import dataclass

from GAVEL.app.dtos.canvas_consent_form_entry import ConsentFormEntry


@dataclass(frozen=True)
class DownselectConsentedStudentsRequest:
    entries: tuple[ConsentFormEntry, ...]


@dataclass(frozen=True)
class DownselectConsentedStudentsResult:
    consented_ids: tuple[int, ...]
    included_count: int
    excluded_count: int


class DownselectConsentedStudentsUseCase:
    def execute(
        self,
        request: DownselectConsentedStudentsRequest,
    ) -> DownselectConsentedStudentsResult:
        latest_by_student: dict[int, ConsentFormEntry] = {}

        for entry in request.entries:
            current = latest_by_student.get(entry.sis_id)
            if current is None or entry.attempt > current.attempt:
                latest_by_student[entry.sis_id] = entry

        consented_ids: list[int] = []
        excluded_count = 0

        for entry in latest_by_student.values():
            if not entry.consented:
                excluded_count += 1
                continue

            lms_name = entry.lms_name.lower().strip()
            response = entry.name_response.lower().strip()

            if not response:
                excluded_count += 1
                continue

            if response == lms_name:
                consented_ids.append(entry.sis_id)
                continue

            lms_chunks = [chunk for chunk in lms_name.split() if chunk]
            if any(chunk in response for chunk in lms_chunks):
                consented_ids.append(entry.sis_id)
                continue

            excluded_count += 1

        return DownselectConsentedStudentsResult(
            consented_ids=tuple(sorted(consented_ids)),
            included_count=len(consented_ids),
            excluded_count=excluded_count,
        )