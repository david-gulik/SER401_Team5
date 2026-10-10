from __future__ import annotations

from collections.abc import Sequence

from GAVEL.app.dtos.proxy_grade_mapping import ProxyGradeMapping
from GAVEL.app.dtos.rubric_definition import RubricCriterionDefinition, RubricDefinition


class UnmatchedProxyCriterionError(ValueError):
    """A proxy-grade mapping's criterion has no matching rubric criterion."""

    def __init__(self, unmatched: Sequence[str]) -> None:
        self.unmatched = tuple(unmatched)
        super().__init__(f"No rubric criterion matches: {', '.join(self.unmatched)}")


def _normalize(text: str) -> str:
    return "".join(text.split()).casefold()


def match_proxy_criteria_to_rubric(
    mapping: ProxyGradeMapping, rubric: RubricDefinition
) -> dict[str, RubricCriterionDefinition]:
    """Matches each proxy-grade criterion to its rubric criterion by name.

    Names are compared with all whitespace removed and case ignored, since
    the two sources are authored independently and can drift by formatting
    alone (e.g. "course_insert::memory" vs "course_insert:: memory"). Raises
    UnmatchedProxyCriterionError, naming every proxy criterion with no match
    at once, so a mapping that has drifted from its rubric is caught early.
    """
    by_normalized_name = {_normalize(c.description): c for c in rubric.criteria}

    unmatched = [
        criterion.name
        for criterion in mapping.criteria
        if _normalize(criterion.name) not in by_normalized_name
    ]
    if unmatched:
        raise UnmatchedProxyCriterionError(unmatched)

    return {
        criterion.name: by_normalized_name[_normalize(criterion.name)]
        for criterion in mapping.criteria
    }
