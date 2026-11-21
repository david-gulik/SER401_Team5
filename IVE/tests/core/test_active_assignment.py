from __future__ import annotations

from GAVEL.core.active_assignment import ActiveAssignment, AssignmentPick

PICK = AssignmentPick("ser334_25fc_82931", 9, "anon_4821")
OTHER = AssignmentPick("ser334_25fc_82931", 3)


def test_starts_with_nothing_picked(qapp):
    assert ActiveAssignment().pick is None


def test_select_notifies_subscribers(qapp):
    active = ActiveAssignment()
    received: list[AssignmentPick | None] = []
    active.changed.connect(received.append)

    active.select(PICK)

    assert active.pick == PICK
    assert received == [PICK]


def test_selecting_the_same_pick_again_is_silent(qapp):
    active = ActiveAssignment()
    active.select(PICK)
    received: list[AssignmentPick | None] = []
    active.changed.connect(received.append)

    active.select(AssignmentPick("ser334_25fc_82931", 9, "anon_4821"))

    assert received == []


def test_select_none_clears_the_pick_and_notifies(qapp):
    active = ActiveAssignment()
    active.select(PICK)
    received: list[AssignmentPick | None] = []
    active.changed.connect(received.append)

    active.select(None)

    assert active.pick is None
    assert received == [None]


def test_hand_off_picks_then_asks_for_the_page(qapp):
    active = ActiveAssignment()
    events: list[tuple[str, object]] = []
    active.changed.connect(lambda pick: events.append(("changed", pick)))
    active.page_requested.connect(lambda page_id: events.append(("page", page_id)))

    active.hand_off(PICK, "inspect_grades")

    assert events == [("changed", PICK), ("page", "inspect_grades")]

    active.hand_off(PICK, "inspect_grades")

    # The same pick again still shows the page.
    assert events[2:] == [("page", "inspect_grades")]

    active.hand_off(OTHER, "inspect_grades")

    assert events[3:] == [("changed", OTHER), ("page", "inspect_grades")]
