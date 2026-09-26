from __future__ import annotations

import pytest

from GAVEL.app.usecases.generate_anonymous_id_map import (
    GenerateAnonymousIdMapRequest,
    GenerateAnonymousIdMapUseCase,
)

STUDENT_IDS = {100001, 100002, 100003, 100004}


@pytest.fixture
def use_case() -> GenerateAnonymousIdMapUseCase:
    return GenerateAnonymousIdMapUseCase()


class TestHappyPath:
    def test_execute_returns_map_for_every_student(self, use_case):
        request = GenerateAnonymousIdMapRequest(
            student_ids=STUDENT_IDS,
            seed=42,
        )

        result = use_case.execute(request)

        assert set(result.id_map.keys()) == STUDENT_IDS

    def test_generated_ids_are_unique(self, use_case):
        request = GenerateAnonymousIdMapRequest(
            student_ids=STUDENT_IDS,
            seed=42,
        )

        result = use_case.execute(request)

        anonymous_ids = list(result.id_map.values())

        assert len(anonymous_ids) == len(set(anonymous_ids))

    def test_generated_ids_are_in_four_digit_range(self, use_case):
        request = GenerateAnonymousIdMapRequest(
            student_ids=STUDENT_IDS,
            seed=42,
        )

        result = use_case.execute(request)

        assert all(1000 <= anonymous_id <= 9999 for anonymous_id in result.id_map.values())

    def test_same_seed_produces_same_map(self, use_case):
        request = GenerateAnonymousIdMapRequest(
            student_ids=STUDENT_IDS,
            seed=42,
        )

        first = use_case.execute(request)
        second = use_case.execute(request)

        assert first.id_map == second.id_map

    def test_empty_student_set_returns_empty_map(self, use_case):
        request = GenerateAnonymousIdMapRequest(
            student_ids=set(),
            seed=42,
        )

        result = use_case.execute(request)

        assert result.id_map == {}


class TestValidation:
    def test_raises_when_more_than_9000_student_ids(self, use_case):
        student_ids = set(range(9001))

        request = GenerateAnonymousIdMapRequest(
            student_ids=student_ids,
            seed=42,
        )

        with pytest.raises(
            ValueError,
            match="Cannot generate more than 9000 unique anonymous IDs",
        ):
            use_case.execute(request)
