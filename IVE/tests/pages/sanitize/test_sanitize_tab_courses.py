from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt

from GAVEL.pages.sanitize.tabs import OPEN_LOCATION_TEXT, SanitizeTab
from GAVEL.pages.sanitize.viewmodel import CourseFilter, SanitizeViewModel
from tests.pages.sanitize.course_folders import ANONYMIZED, CHANGED_AFTER, build_course

NEW = "ser222_26f_11111"
STALE = "ser316_26s_33333"
BLOCKED = "ser334_26u_44444"


@pytest.fixture
def vm(qapp, tmp_path: Path) -> SanitizeViewModel:
    build_course(tmp_path, NEW, gradebook=False, rubric_assessments=2)
    build_course(tmp_path, STALE, inputs_at=CHANGED_AFTER, anonymized_at=ANONYMIZED)
    build_course(tmp_path, BLOCKED, consent_form=False)
    vm = SanitizeViewModel(default_workspace_root=tmp_path)
    vm.reload()
    return vm


@pytest.fixture
def tab(qapp, theme, vm: SanitizeViewModel):
    tab = SanitizeTab(theme, vm)
    yield tab
    tab.deleteLater()


def top_level_texts(tab: SanitizeTab, column: int) -> list[str]:
    tree = tab.course_tree
    return [tree.topLevelItem(i).text(column) for i in range(tree.topLevelItemCount())]


def course_item(tab: SanitizeTab, folder_name: str):
    tree = tab.course_tree
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.data(0, Qt.ItemDataRole.UserRole) == folder_name:
            return item
    raise AssertionError(f"{folder_name} not in tree")


def dump(item, depth: int = 0) -> list[str]:
    """Each row under ``item`` as "<indent><name> | <status>", depth first."""
    lines = []
    for i in range(item.childCount()):
        child = item.child(i)
        lines.append(f"{'  ' * depth}{child.text(0)} | {child.text(4)}")
        lines.extend(dump(child, depth + 1))
    return lines


class TestTree:
    def test_one_row_per_course_with_its_status(self, tab):
        assert top_level_texts(tab, 0) == ["SER 222 (11111)", "SER 316 (33333)", "SER 334 (44444)"]
        assert top_level_texts(tab, 1) == ["Fall 2026", "Spring 2026", "Summer 2026"]
        assert top_level_texts(tab, 4) == [
            "●  Not anonymized",
            "●  Out of date",
            "●  No consent form",
        ]

    def test_consent_form_column_counts_consenting_students_or_says_missing(self, tab):
        assert top_level_texts(tab, 2) == ["3 of 4 consented", "3 of 4 consented", "Missing"]

    def test_last_anonymized_column(self, tab):
        assert top_level_texts(tab, 3) == ["Never", "2026-09-27 14:02", "Never"]

    def test_course_mirrors_original_and_anonymized_folders(self, tab):
        assert dump(course_item(tab, NEW)) == [
            "original/ | ●  Up to date",
            "  consent_form.csv | ●  Up to date",
            "  roster.csv | ●  Up to date",
            "  gradebook.csv | ○  Missing",
            "  assignments/ | ●  Up to date",
            "    7216970_m1/ | ●  Up to date",
            "      rubric_assessments.json | ●  Up to date",
            "    7216971_m2/ | ●  Up to date",
            "      rubric_assessments.json | ●  Up to date",
            "anonymized/ | ○  Missing",
            "  consent_form.csv | ○  Missing",
            "  roster.csv | ○  Missing",
            "  gradebook.csv | ○  Missing",
            "  assignments/ | ○  Missing",
            "    7216970_m1/ | ○  Missing",
            "      rubric_assessments.json | ○  Missing",
            "    7216971_m2/ | ○  Missing",
            "      rubric_assessments.json | ○  Missing",
        ]

    def test_stale_copies_and_their_folder_are_out_of_date(self, tab):
        lines = dump(course_item(tab, STALE))
        anonymized = lines[lines.index("anonymized/ | ●  Out of date") :]

        assert anonymized == [
            "anonymized/ | ●  Out of date",
            "  consent_form.csv | ●  Out of date",
            "  roster.csv | ●  Out of date",
            "  gradebook.csv | ●  Out of date",
        ]

    def test_expanded_folders_stay_expanded_after_a_reload(self, tab, vm, tmp_path):
        course_item(tab, NEW).child(0).setExpanded(True)
        build_course(tmp_path, "ser440_26f_55555")

        vm.reload()

        assert course_item(tab, NEW).child(0).isExpanded()

    def test_filter_buttons_show_counts_and_filter_the_tree(self, tab, vm):
        assert tab.filter_button(CourseFilter.NOT_UP_TO_DATE).text() == "Not up to date (3)"

        tab.filter_button(CourseFilter.UP_TO_DATE).click()

        assert vm.get_state().course_filter is CourseFilter.UP_TO_DATE
        assert tab.course_tree.topLevelItemCount() == 0
        assert tab.filter_button(CourseFilter.UP_TO_DATE).isChecked()


class TestSelecting:
    def test_clicking_a_course_selects_it_and_expands_it(self, tab, vm):
        item = course_item(tab, STALE)

        tab.course_tree.setCurrentItem(item)

        assert vm.get_state().selected_course == STALE
        assert item.isExpanded()

    def test_clicking_a_file_row_selects_its_course(self, tab, vm):
        item = course_item(tab, NEW)
        item.setExpanded(True)

        tab.course_tree.setCurrentItem(item.child(0).child(2))

        assert vm.get_state().selected_course == NEW
        assert tab.course_tree.currentItem() is item

    def test_selection_from_the_view_model_highlights_the_row(self, tab, vm):
        vm.select_course(BLOCKED)

        assert tab.course_tree.currentItem() is course_item(tab, BLOCKED)


class TestBanner:
    def test_out_of_date_course_warns_about_new_ids(self, tab, vm):
        vm.select_course(STALE)

        text = tab.banner_label.text()
        assert tab.banner_label.isVisibleTo(tab)
        assert text.startswith("Out of date")
        assert "new anonymous ID" in text
        assert tab.banner_label.property("role") == "caution"

    def test_missing_consent_form_is_a_warning(self, tab, vm):
        vm.select_course(BLOCKED)

        assert "No consent form" in tab.banner_label.text()
        assert tab.banner_label.property("role") == "warning"

    def test_course_never_anonymized_has_no_banner(self, tab, vm):
        vm.select_course(NEW)

        assert not tab.banner_label.isVisibleTo(tab)


class TestWorkspaceInput:
    def test_typing_a_workspace_rescans_it(self, tab, vm, tmp_path_factory):
        other = tmp_path_factory.mktemp("typed_workspace")
        build_course(other, "ser101_26f_99999")

        tab.workspace_input.setText(str(other))
        tab.workspace_input.editingFinished.emit()

        assert vm.get_state().workspace_root == str(other)
        assert top_level_texts(tab, 0) == ["SER 101 (99999)"]


class TestEmptyWorkspace:
    def test_empty_workspace_explains_what_to_do(self, qapp, theme, tmp_path):
        vm = SanitizeViewModel(default_workspace_root=tmp_path)
        vm.reload()

        tab = SanitizeTab(theme, vm)

        assert tab.course_tree.topLevelItemCount() == 0
        assert "No course folders found" in tab.empty_label.text()
        tab.deleteLater()


class TestOpenFolderLocation:
    @pytest.fixture
    def opened(self, qapp, theme, vm):
        opened: list[Path] = []
        tab = SanitizeTab(theme, vm, open_location=opened.append)
        yield tab, opened
        tab.deleteLater()

    def trigger(self, tab, item):
        [action] = tab.context_menu_for(item).actions()
        assert action.text() == OPEN_LOCATION_TEXT
        action.trigger()
        return action

    def test_course_row_opens_the_course_folder(self, opened, tmp_path):
        tab, paths = opened

        self.trigger(tab, course_item(tab, NEW))

        assert paths == [tmp_path / "courses" / NEW]

    def test_file_row_opens_that_file(self, opened, tmp_path):
        tab, paths = opened
        roster = course_item(tab, NEW).child(0).child(1)

        self.trigger(tab, roster)

        assert paths == [tmp_path / "courses" / NEW / "original" / "roster.csv"]

    def test_missing_file_cannot_be_opened(self, opened):
        tab, paths = opened
        gradebook = course_item(tab, NEW).child(0).child(2)

        action = self.trigger(tab, gradebook)

        assert not action.isEnabled()
        assert paths == []

    def test_folder_that_does_not_exist_cannot_be_opened(self, opened):
        tab, paths = opened
        anonymized = course_item(tab, NEW).child(1)

        action = self.trigger(tab, anonymized)

        assert not action.isEnabled()
        assert paths == []
