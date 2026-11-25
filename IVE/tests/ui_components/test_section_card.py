from __future__ import annotations

from PyQt6.QtWidgets import QPushButton, QSizePolicy

from GAVEL.ui_components.section_card import SectionCard

LONG_SUBTITLE = (
    "Module 9 · ser334_m9_v1_steady · 12 submissions × 10 runs · 30 workers · 5 min timeout · "
    "and a few more words so it is longer than a narrow window"
)


def test_a_long_subtitle_wraps_instead_of_widening_the_card(qapp, theme):
    card = SectionCard(theme, "Set up")
    card.add_action(QPushButton("Cancel"))

    card.set_subtitle(LONG_SUBTITLE)

    assert card.subtitle == LONG_SUBTITLE
    assert card._subtitle.wordWrap()
    assert card._subtitle.sizePolicy().horizontalPolicy() is QSizePolicy.Policy.Expanding
    # A narrow window can shrink the header well below the subtitle's one-line width,
    # so the action button stays in view instead of being pushed past the edge.
    one_line = card._subtitle.fontMetrics().horizontalAdvance(LONG_SUBTITLE)
    assert card._header.minimumSizeHint().width() < one_line / 2

    card.set_subtitle("")

    assert not card._subtitle.isVisibleTo(card)


def test_a_title_suffix_sits_beside_the_title_and_actions_at_the_edge(qapp, theme):
    card = SectionCard(theme, "Results")
    change = QPushButton("Change")
    far = QPushButton("Cancel")
    card.add_action(far)

    card.add_title_suffix(change)

    layout = card._header.layout()
    assert layout.indexOf(change) == 1
    assert far.parent() is card._actions
    assert layout.indexOf(card._actions) == layout.count() - 1
