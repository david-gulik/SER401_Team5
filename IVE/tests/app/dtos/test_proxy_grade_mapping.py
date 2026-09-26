from __future__ import annotations

import pytest

from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier


def test_tier_without_required_tests_is_rejected() -> None:
    with pytest.raises(ValueError):
        Tier(1.0)


def test_test_names_lists_each_name_once_in_first_seen_order() -> None:
    mapping = ProxyGradeMapping(
        name="toy",
        criteria=(
            Criterion("first", (Tier(2.0, all_of=("A", "B")), Tier(1.0, all_of=("A",)))),
            Criterion("second", (Tier(3.0, any_of=("C", "A")),)),
        ),
    )

    assert mapping.test_names() == ("A", "B", "C")


@pytest.mark.parametrize("at_least", [0, 3])
def test_at_least_outside_the_any_of_range_is_rejected(at_least: int) -> None:
    with pytest.raises(ValueError):
        Tier(1.0, any_of=("A", "B"), at_least=at_least)
