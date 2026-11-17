from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt

from GAVEL.pages.sanitize.consent_review import (
    NO_CONSENT_FORM_TEXT,
    NO_COURSE_TEXT,
    OVERRIDE_TEXT,
    REMOVE_OVERRIDE_TEXT,
    TILES,
)
from GAVEL.pages.sanitize.tabs import SanitizeTab
from GAVEL.pages.sanitize.viewmodel import ConsentFilter, SanitizeViewModel
from tests.pages.sanitize.course_folders import EVERY_OUTCOME, build_course, write_students

REVIEWED = "ser222_26f_11111"
NO_FORM = "ser334_26u_44444"


@pytest.fixture
def vm(qapp, tmp_path: Path) -> SanitizeViewModel:
    write_students(build_course(tmp_path, REVIEWED), EVERY_OUTCOME)
    build_course(tmp_path, NO_FORM, consent_form=False)
    vm = SanitizeViewModel(default_workspace_root=tmp_path)
    vm.reload()
    return vm


@pytest.fixture
def card(qapp, theme, vm):
    tab = SanitizeTab(theme, vm)
    yield tab.consent_card
    tab.deleteLater()


def column(card, index: int) -> list[str]:
    table = card.table
    return [table.item(row, index).text() for row in range(table.rowCount())]


class TestBeforeReviewing:
    def test_asks_for_a_course_until_one_is_selected(self, card):
        assert card.placeholder.text() == NO_COURSE_TEXT
        assert not card.table.isVisibleTo(card)

    def test_course_without_a_consent_form_says_so(self, card, vm):
        vm.select_course(NO_FORM)

        assert card.placeholder.text() == NO_CONSENT_FORM_TEXT
        assert not card.table.isVisibleTo(card)

    def test_unreadable_consent_form_shows_the_error(self, card, vm, tmp_path):
        form = tmp_path / "courses" / REVIEWED / "original" / "consent_form.csv"
        form.write_text("nonsense\n", encoding="utf-8")

        vm.select_course(REVIEWED)

        assert card.error_label.isVisibleTo(card)
        assert not card.table.isVisibleTo(card)


class TestReviewing:
    @pytest.fixture(autouse=True)
    def selected(self, vm):
        vm.select_course(REVIEWED)

    def test_subtitle_names_the_course(self, card):
        assert card.subtitle == "SER 222 (11111)  ·  Fall 2026"

    def test_tiles_count_each_outcome(self, card):
        counts = {tile_filter: card.tile(tile_filter).count_text for tile_filter, *_ in TILES}

        assert counts == {
            ConsentFilter.INCLUDED: "2",
            ConsentFilter.DECLINED: "1",
            ConsentFilter.NAME_PROBLEM: "3",
            ConsentFilter.NO_RESPONSE: "1",
        }

    def test_segments_show_counts(self, card):
        assert card.segment(ConsentFilter.ALL).text() == "All (7)"
        assert card.segment(ConsentFilter.INCLUDED).text() == "Included (2)"
        assert card.segment(ConsentFilter.EXCLUDED).text() == "Excluded (5)"

    def test_one_row_per_student_with_the_reason(self, card):
        assert column(card, 0) == [
            "Chinedu Okafor",
            "Devon Brooks",
            "Hannah Fischer",
            "Kenji Ishikawa",
            "Luca Esposito",
            "Marisol Alvarez",
            "Omar Haddad",
        ]
        assert column(card, 5) == [
            "▲  Name mismatch",
            "✓  Included",
            "✕  Declined",
            "▲  Possible typo",
            "▲  Name blank",
            "✓  Included",
            "—  No response",
        ]

    def test_answers_columns(self, card):
        assert column(card, 2) == ["1", "1", "1", "1", "1", "2", "—"]
        assert column(card, 3) == [
            "Nedu O.",
            "Devon",
            "Hannah Fischer",
            "Kenij Ishikwa",
            "(blank)",
            "Marisol Alvarez",
            "—",
        ]
        assert column(card, 4) == ["Yes", "Yes", "No", "Yes", "Yes", "Yes", "—"]

    def test_clicking_a_tile_filters_and_keeps_excluded_lit(self, card, vm):
        card.tile(ConsentFilter.NAME_PROBLEM).click()

        assert vm.get_state().consent_filter is ConsentFilter.NAME_PROBLEM
        assert card.table.rowCount() == 3
        assert card.tile(ConsentFilter.NAME_PROBLEM).isChecked()
        assert card.segment(ConsentFilter.EXCLUDED).isChecked()

    def test_clicking_the_same_tile_again_clears_it(self, card):
        tile = card.tile(ConsentFilter.DECLINED)
        tile.click()
        tile.click()

        assert card.table.rowCount() == 7
        assert card.segment(ConsentFilter.ALL).isChecked()

    def test_segment_filters_the_table(self, card):
        card.segment(ConsentFilter.INCLUDED).click()

        assert column(card, 0) == ["Devon Brooks", "Marisol Alvarez"]

    def test_search_filters_the_table(self, card):
        card.search.setText("haddad")

        assert column(card, 0) == ["Omar Haddad"]


class TestCopying:
    @pytest.fixture(autouse=True)
    def selected(self, vm):
        vm.select_course(REVIEWED)

    def select(self, card, *cells):
        card.table.clearSelection()
        for row, col in cells:
            card.table.item(row, col).setSelected(True)

    def test_cells_can_be_selected(self, card):
        assert card.table.selectionMode() is not card.table.SelectionMode.NoSelection

    def test_one_cell_copies_its_text(self, card):
        self.select(card, (0, 1))

        assert card.copied_text() == "1220440006"

    def test_a_block_copies_as_tab_separated_rows(self, card):
        self.select(card, (0, 0), (0, 1), (1, 0), (1, 1))

        assert card.copied_text() == "Chinedu Okafor\t1220440006\nDevon Brooks\t1220440001"

    def test_result_copies_the_word_without_the_glyph(self, card):
        self.select(card, (0, 5), (1, 5))

        assert card.copied_text() == "Name mismatch\nIncluded"

    def test_copy_puts_the_selection_on_the_clipboard(self, card, qapp):
        self.select(card, (2, 0))

        card.copy_selection()

        assert qapp.clipboard().text() == "Hannah Fischer"

    def test_nothing_selected_copies_nothing(self, card):
        card.table.clearSelection()

        assert card.copied_text() == ""


class TestSorting:
    @pytest.fixture(autouse=True)
    def selected(self, vm):
        vm.select_course(REVIEWED)

    def sort_by(self, card, index: int, order=Qt.SortOrder.AscendingOrder):
        card.table.horizontalHeader().setSortIndicator(index, order)

    def test_starts_sorted_by_student(self, card):
        header = card.table.horizontalHeader()

        assert header.sortIndicatorSection() == 0
        assert card.table.isSortingEnabled()

    def test_student_descending(self, card):
        self.sort_by(card, 0, Qt.SortOrder.DescendingOrder)

        assert column(card, 0)[0] == "Omar Haddad"

    def test_result_sorts_kept_first_then_each_reason(self, card):
        self.sort_by(card, 5)

        assert column(card, 5) == [
            "✓  Included",
            "✓  Included",
            "✕  Declined",
            "▲  Name blank",
            "▲  Possible typo",
            "▲  Name mismatch",
            "—  No response",
        ]

    def test_attempt_sorts_by_number_with_no_attempt_last(self, card):
        self.sort_by(card, 2, Qt.SortOrder.DescendingOrder)
        assert column(card, 2)[0] == "—"

        self.sort_by(card, 2)
        assert column(card, 2)[-1] == "—"
        assert column(card, 2)[-2] == "2"

    def test_sis_id_sorts_numerically(self, card):
        self.sort_by(card, 1)

        ids = column(card, 1)
        assert ids == sorted(ids, key=int)

    def test_sort_survives_filtering(self, card, vm):
        self.sort_by(card, 5)

        vm.set_consent_filter(ConsentFilter.EXCLUDED)

        assert column(card, 5)[0] == "✕  Declined"
        assert card.table.horizontalHeader().sortIndicatorSection() == 5

    def test_copy_follows_the_sorted_order(self, card):
        self.sort_by(card, 0, Qt.SortOrder.DescendingOrder)
        card.table.item(0, 0).setSelected(True)
        card.table.item(1, 0).setSelected(True)

        assert card.copied_text() == "Omar Haddad\nMarisol Alvarez"


def row_menu(card, student: str):
    """The right-click menu for the row showing ``student``. Keep a reference to it
    while using its actions: the menu has no parent, and its actions go with it."""
    return card.build_table_menu(column(card, 0).index(student))


def menu_texts(menu) -> list[str]:
    return [action.text() for action in menu.actions() if action.text()]


def choose(menu, text: str) -> None:
    next(action for action in menu.actions() if action.text() == text).trigger()


class TestOverriding:
    @pytest.fixture(autouse=True)
    def selected(self, vm):
        vm.select_course(REVIEWED)

    def result_of(self, card, student: str) -> str:
        return column(card, 5)[column(card, 0).index(student)]

    @pytest.mark.parametrize("student", ["Kenji Ishikawa", "Chinedu Okafor"])
    def test_typo_and_mismatch_rows_offer_override(self, card, student):
        assert OVERRIDE_TEXT in menu_texts(row_menu(card, student))

    @pytest.mark.parametrize(
        "student", ["Luca Esposito", "Hannah Fischer", "Omar Haddad", "Marisol Alvarez"]
    )
    def test_other_rows_do_not(self, card, student):
        texts = menu_texts(row_menu(card, student))

        assert OVERRIDE_TEXT not in texts
        assert REMOVE_OVERRIDE_TEXT not in texts
        assert "Copy" in texts

    def test_no_row_under_the_cursor_offers_only_copy(self, card):
        menu = card.build_table_menu(-1)

        assert [a.text() for a in menu.actions()] == ["Copy"]

    @pytest.mark.parametrize("student", ["Kenji Ishikawa", "Chinedu Okafor"])
    def test_override_moves_the_student_to_included(self, card, student):
        choose(row_menu(card, student), OVERRIDE_TEXT)

        assert self.result_of(card, student) == "✓  Included (overridden)"
        assert card.tile(ConsentFilter.INCLUDED).count_text == "3"
        assert card.tile(ConsentFilter.NAME_PROBLEM).count_text == "2"

    def test_override_follows_the_sorted_row(self, card):
        card.table.horizontalHeader().setSortIndicator(0, Qt.SortOrder.DescendingOrder)

        choose(row_menu(card, "Kenji Ishikawa"), OVERRIDE_TEXT)

        assert self.result_of(card, "Kenji Ishikawa") == "✓  Included (overridden)"
        assert self.result_of(card, "Chinedu Okafor") == "▲  Name mismatch"

    def test_overridden_rows_show_under_included(self, card):
        choose(row_menu(card, "Kenji Ishikawa"), OVERRIDE_TEXT)

        card.segment(ConsentFilter.INCLUDED).click()

        assert "Kenji Ishikawa" in column(card, 0)

    def test_name_problem_tile_notes_overrides(self, card):
        assert card.tile(ConsentFilter.NAME_PROBLEM).note_text == ""

        choose(row_menu(card, "Kenji Ishikawa"), OVERRIDE_TEXT)
        assert card.tile(ConsentFilter.NAME_PROBLEM).note_text == "1 overridden"

        choose(row_menu(card, "Chinedu Okafor"), OVERRIDE_TEXT)
        assert card.tile(ConsentFilter.NAME_PROBLEM).note_text == "2 overridden"

    def test_only_the_name_problem_tile_gets_a_note(self, card):
        choose(row_menu(card, "Kenji Ishikawa"), OVERRIDE_TEXT)

        notes = {
            f: card.tile(f).note_text for f, *_ in TILES if f is not ConsentFilter.NAME_PROBLEM
        }
        assert set(notes.values()) == {""}

    def test_overrides_load_when_the_course_is_opened_again(self, card, vm, tmp_path):
        choose(row_menu(card, "Kenji Ishikawa"), OVERRIDE_TEXT)

        fresh = SanitizeViewModel(default_workspace_root=tmp_path)
        fresh.reload()
        fresh.select_course(REVIEWED)

        assert fresh.get_state().overridden_count == 1

    def test_overridden_row_offers_remove(self, card):
        choose(row_menu(card, "Kenji Ishikawa"), OVERRIDE_TEXT)

        assert OVERRIDE_TEXT not in menu_texts(row_menu(card, "Kenji Ishikawa"))
        choose(row_menu(card, "Kenji Ishikawa"), REMOVE_OVERRIDE_TEXT)

        assert self.result_of(card, "Kenji Ishikawa") == "▲  Possible typo"
        assert card.tile(ConsentFilter.NAME_PROBLEM).note_text == ""

    def test_failed_override_shows_why_and_keeps_the_table(self, card, vm, tmp_path):
        menu = row_menu(card, "Kenji Ishikawa")
        # The student declines on a new attempt after the table was drawn.
        students = list(EVERY_OUTCOME)
        students[5] = ("Kenji Ishikawa", "Kenij Ishikwa", False, 1)
        write_students(tmp_path / "courses" / REVIEWED, tuple(students))

        choose(menu, OVERRIDE_TEXT)

        assert "Only a possible typo or a name mismatch" in card.error_label.text()
        assert card.error_label.isVisibleTo(card)
        assert card.table.isVisibleTo(card)
        assert self.result_of(card, "Kenji Ishikawa") == "✕  Declined"
