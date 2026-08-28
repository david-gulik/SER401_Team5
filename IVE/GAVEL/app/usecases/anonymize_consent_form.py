from __future__ import annotations

from dataclasses import dataclass

from GAVEL.app.dtos.canvas_consent_form_entry import ConsentFormEntry


@dataclass(frozen=True)
class AnonymizeConsentFormRequest:
    entries: tuple[ConsentFormEntry, ...]
    id_map: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class AnonymizeConsentFormResult:
    entries: tuple[ConsentFormEntry, ...]
    skipped_count: int


class AnonymizeConsentFormUseCase:
    def execute(
        self,
        request: AnonymizeConsentFormRequest,
    ) -> AnonymizeConsentFormResult:
        id_map = dict(request.id_map)

        anonymized: list[ConsentFormEntry] = []
        skipped_count = 0

        for entry in request.entries:
            if entry.sis_id not in id_map:
                skipped_count += 1
                continue

            anonymous_id = id_map[entry.sis_id]

            anonymized.append(
                ConsentFormEntry(
                    sis_id=anonymous_id,
                    lms_name=f"Anon{anonymous_id} Anon",
                    attempt=entry.attempt,
                    name_response="",
                    consented=entry.consented,
                )
            )

        return AnonymizeConsentFormResult(
            entries=tuple(anonymized),
            skipped_count=skipped_count,
        )
