from __future__ import annotations

from dataclasses import dataclass

from GAVEL.app.dtos.asu_roster import RosterStudent


@dataclass(frozen=True)
class AnonymizeRosterRequest:
    students: tuple[RosterStudent, ...]
    consented_ids: tuple[int, ...]
    id_map: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class AnonymizeRosterResult:
    students: tuple[RosterStudent, ...]
    skipped_count: int
    excluded_count: int


class AnonymizeRosterUseCase:
    def execute(self, request: AnonymizeRosterRequest) -> AnonymizeRosterResult:
        id_map = dict(request.id_map)
        consented = set(request.consented_ids)

        anonymized: list[RosterStudent] = []
        skipped_count = 0
        excluded_count = 0

        for student in request.students:
            real_id = int(student.id)

            if real_id not in id_map:
                skipped_count += 1
                continue

            if real_id not in consented:
                excluded_count += 1
                continue

            anonymous_id = id_map[real_id]
            anon_str = str(anonymous_id)

            anonymized.append(
                RosterStudent(
                    id=anon_str,
                    posting_id=f"{anon_str}-000",
                    first_name="Anon",
                    last_name=f"Anon{anon_str}",
                    status=student.status,
                    units=student.units,
                    grade_basis=student.grade_basis,
                    program_and_plan=student.program_and_plan,
                    academic_level=student.academic_level,
                    asurite=f"aanon{anon_str}",
                    residency=student.residency,
                    zoom_email=f"aanon{anon_str}@anon.com",
                )
            )

        anonymized = sorted(anonymized, key=lambda s: s.last_name)

        return AnonymizeRosterResult(
            students=tuple(anonymized),
            skipped_count=skipped_count,
            excluded_count=excluded_count,
        )
