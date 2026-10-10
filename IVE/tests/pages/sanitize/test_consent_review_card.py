from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt

from GAVEL.pages.sanitize.consent_review import NO_CONSENT_FORM_TEXT, NO_COURSE_TEXT, TILES
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
