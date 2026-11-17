from __future__ import annotations

from GAVEL.core.navigation_drawer import NavigationDrawer
from GAVEL.core.page_registry import PageRegistry, PageSpec


def spec(page_id: str, group: str, order: int) -> PageSpec:
    return PageSpec(
        page_id=page_id,
        title=page_id.title(),
        icon_text="",
        factory=lambda ctx: None,
        order=order,
        group=group,
    )


def drawer(theme) -> NavigationDrawer:
    registry = PageRegistry()
    registry.register(spec("analytics", "Analysis", 40))
    registry.register(spec("settings", "General", 20))
    registry.register(spec("home", "General", 10))
    registry.register(spec("download", "Preparation", 30))
    return NavigationDrawer(theme, registry.list_pages(), lambda page_id: None)


def test_each_group_gets_one_heading_in_sidebar_order(qapp, theme):
    nav = drawer(theme)

    assert [label.text() for label in nav.section_labels] == [
        "GENERAL",
        "PREPARATION",
        "ANALYSIS",
    ]


def test_rules_sit_only_between_groups(qapp, theme):
    nav = drawer(theme)

    assert len(nav.dividers) == 2


def test_collapsing_hides_the_headings_but_keeps_the_rules(qapp, theme):
    nav = drawer(theme)

    nav.toggle()

    assert all(label.isHidden() for label in nav.section_labels)
    assert not any(line.isHidden() for line in nav.dividers)

    nav.toggle()

    assert not any(label.isHidden() for label in nav.section_labels)
