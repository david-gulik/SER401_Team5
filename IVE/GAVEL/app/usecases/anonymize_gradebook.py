from __future__ import annotations

from dataclasses import dataclass

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook, GradebookStudentRow


@dataclass(frozen=True)
class AnonymizeGradebookRequest:
    gradebook: CanvasGradebook
    consented_ids: tuple[int, ...]
    id_map: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class AnonymizeGradebookResult:
    gradebook: CanvasGradebook
    skipped_count: int
    excluded_count: int


class AnonymizeGradebookUseCase:
    def execute(self, request: AnonymizeGradebookRequest) -> AnonymizeGradebookResult:
        id_map = dict(request.id_map)
        consented = set(request.consented_ids)

        anonymized_rows: list[GradebookStudentRow] = []
        skipped_count = 0
        excluded_count = 0

        for row in request.gradebook.rows:
            real_id = row.canvas_id

            if real_id not in id_map:
                skipped_count += 1
                continue

            if real_id not in consented:
                excluded_count += 1
                continue

            anonymous_id = id_map[real_id]

            anonymized_rows.append(
                GradebookStudentRow(
                    student_name=f"Anon{anonymous_id}, Anon",
                    canvas_id=anonymous_id,
                    sis_login_id=f"aanon{anonymous_id}",
                    section=row.section,
                    assignment_scores=row.assignment_scores,
                )
            )

        anonymized_rows = sorted(anonymized_rows, key=lambda r: r.student_name.split(",")[0])

        return AnonymizeGradebookResult(
            gradebook=CanvasGradebook(
                columns=request.gradebook.columns,
                rows=tuple(anonymized_rows),
            ),
            skipped_count=skipped_count,
            excluded_count=excluded_count,
        )
