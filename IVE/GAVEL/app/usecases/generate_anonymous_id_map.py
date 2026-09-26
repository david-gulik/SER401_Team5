from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerateAnonymousIdMapRequest:
    student_ids: set[int]
    seed: int | None = None


@dataclass(frozen=True)
class GenerateAnonymousIdMapResult:
    id_map: dict[int, int]


class GenerateAnonymousIdMapUseCase:
    def execute(self, request: GenerateAnonymousIdMapRequest) -> GenerateAnonymousIdMapResult:
        if len(request.student_ids) > 9000:
            raise ValueError("Cannot generate more than 9000 unique anonymous IDs")

        rng = random.Random(request.seed)

        anonymous_ids = rng.sample(
            range(1000, 10000),
            len(request.student_ids),
        )

        id_map = dict(
            zip(
                sorted(request.student_ids),
                anonymous_ids,
                strict=True,
            )
        )

        return GenerateAnonymousIdMapResult(id_map=id_map)
