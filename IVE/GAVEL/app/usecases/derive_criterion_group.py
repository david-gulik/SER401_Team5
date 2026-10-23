from __future__ import annotations

_GROUP_SEPARATOR = "::"


def derive_criterion_group(criterion_name: str) -> str:
    """The larger requirement a criterion belongs to, from its name.

    Criteria that together score one larger requirement share a name prefix
    before "::", as in "course_insert::memory" and "course_drop::memory" in
    the SER334 Module 2 mapping. A criterion with no "::" is its own group.
    """
    group, _, _ = criterion_name.partition(_GROUP_SEPARATOR)
    return group.strip()
