from __future__ import annotations

from GAVEL.core.page_registry import PageRegistry, PageSpec


def spec(page_id: str, group: str, order: int) -> PageSpec:
    return PageSpec(
        page_id=page_id,
        title=page_id,
        icon_text="",
        factory=lambda ctx: None,
        order=order,
        group=group,
    )


def page_ids(registry: PageRegistry) -> list[str]:
    return [page.page_id for page in registry.list_pages()]


def test_groups_follow_group_order_not_the_alphabet():
    registry = PageRegistry()
    registry.register(spec("analytics", "Analytics", 10))
    registry.register(spec("download", "Integrations", 10))
    registry.register(spec("home", "General", 10))

    assert page_ids(registry) == ["home", "download", "analytics"]


def test_pages_within_a_group_follow_their_order():
    registry = PageRegistry()
    registry.register(spec("settings", "General", 20))
    registry.register(spec("home", "General", 10))

    assert page_ids(registry) == ["home", "settings"]


def test_unlisted_groups_go_last_sorted_by_name():
    registry = PageRegistry()
    registry.register(spec("zeta", "Zeta", 10))
    registry.register(spec("beta", "Beta", 10))
    registry.register(spec("analytics", "Analytics", 10))

    assert page_ids(registry) == ["analytics", "beta", "zeta"]


def test_app_pages_put_analytics_last():
    import GAVEL.app.main  # noqa: F401

    ids = page_ids(PageRegistry.get())

    assert ids[0] == "home"
    assert ids[-1] == "analytics"
