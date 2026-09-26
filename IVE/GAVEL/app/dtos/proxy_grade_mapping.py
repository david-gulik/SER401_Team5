from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tier:
    """Points awarded when the required tests passed.

    A tier is satisfied when every test in all_of passed and, if any_of is
    given, at least at_least of the tests in any_of passed. Tests are matched
    by a substring of their name.
    """

    points: float
    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()
    at_least: int = 1

    def __post_init__(self) -> None:
        if not self.all_of and not self.any_of:
            raise ValueError("A tier needs at least one required test.")
        if self.any_of and not 1 <= self.at_least <= len(self.any_of):
            raise ValueError("at_least must be between 1 and the number of any_of tests.")


@dataclass(frozen=True)
class Criterion:
    """One rubric criterion.

    Tiers are checked in order and the first satisfied tier wins. A criterion
    with no satisfied tier scores 0.
    """

    name: str
    tiers: tuple[Tier, ...]


@dataclass(frozen=True)
class ProxyGradeMapping:
    """The rules that turn one assignment's autograder tests into rubric criterion scores."""

    name: str
    criteria: tuple[Criterion, ...]

    def test_names(self) -> tuple[str, ...]:
        """Every test name the mapping refers to, once each, in first-seen order."""
        seen: dict[str, None] = {}
        for criterion in self.criteria:
            for tier in criterion.tiers:
                for name in (*tier.all_of, *tier.any_of):
                    seen.setdefault(name)
        return tuple(seen)
