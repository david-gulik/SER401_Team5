from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.pages.sanitize.viewmodel import CourseFilter, SanitizeViewModel
from tests.pages.sanitize.course_folders import ANONYMIZED, CHANGED_AFTER, build_course

NEW = "ser222_26f_11111"
CURRENT = "ser222_26f_22222"
STALE = "ser316_26s_33333"
BLOCKED = "ser334_26u_44444"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    build_course(tmp_path, NEW, canvas_course_name="Data Structures and Algorithms")
    build_course(tmp_path, CURRENT, anonymized_at=ANONYMIZED)
    build_course(tmp_path, STALE, inputs_at=CHANGED_AFTER, anonymized_at=ANONYMIZED)
    build_course(tmp_path, BLOCKED, consent_form=False)
    return tmp_path


@pytest.fixture
def vm(qapp, workspace: Path) -> SanitizeViewModel:
    vm = SanitizeViewModel(default_workspace_root=workspace)
    vm.reload()
    return vm


def visible(vm: SanitizeViewModel) -> list[str]:
    return [course.folder_name for course in vm.get_state().visible_courses]


class TestLoading:
    def test_reload_lists_every_course(self, vm):
        assert visible(vm) == [NEW, CURRENT, STALE, BLOCKED]

    def test_nothing_is_selected_at_first(self, vm):
        assert vm.get_state().selected_course is None

    def test_reload_picks_up_a_new_course(self, vm, workspace):
        build_course(workspace, "ser440_26f_55555")

        vm.reload()

        assert "ser440_26f_55555" in visible(vm)

    def test_state_change_is_announced(self, vm, workspace):
        seen = []
        vm.state_changed.connect(seen.append)
        build_course(workspace, "ser440_26f_55555")

        vm.reload()

        assert seen and seen[-1] is vm.get_state()


class TestFilterAndSearch:
    def test_not_up_to_date_includes_new_stale_and_blocked(self, vm):
        vm.set_course_filter(CourseFilter.NOT_UP_TO_DATE)

        assert visible(vm) == [NEW, STALE, BLOCKED]

    def test_up_to_date_shows_only_current_courses(self, vm):
        vm.set_course_filter(CourseFilter.UP_TO_DATE)

        assert visible(vm) == [CURRENT]

    def test_filter_counts(self, vm):
        state = vm.get_state()

        assert state.filter_count(CourseFilter.ALL) == 4
        assert state.filter_count(CourseFilter.NOT_UP_TO_DATE) == 3
        assert state.filter_count(CourseFilter.UP_TO_DATE) == 1

    @pytest.mark.parametrize(
        ("search", "expected"),
        [
            ("ser 316", [STALE]),
            ("33333", [STALE]),
            ("summer 2026", [BLOCKED]),
            ("data structures", [NEW]),
            ("SER222", [NEW, CURRENT]),
        ],
    )
    def test_search_matches_course_class_term_and_canvas_name(self, vm, search, expected):
        vm.set_course_search(search)

        assert visible(vm) == expected

    def test_search_and_filter_combine(self, vm):
        vm.set_course_search("ser 222")
        vm.set_course_filter(CourseFilter.UP_TO_DATE)

        assert visible(vm) == [CURRENT]


class TestSelection:
    def test_select_course(self, vm):
        vm.select_course(STALE)

        assert vm.get_state().selected_summary.folder_name == STALE

    def test_selection_survives_reload(self, vm):
        vm.select_course(STALE)

        vm.reload()

        assert vm.get_state().selected_course == STALE

    def test_selection_is_dropped_when_the_course_folder_is_gone(self, vm, workspace):
        vm.select_course(NEW)
        (workspace / "courses" / NEW).rename(workspace / "courses" / "not_a_course")

        vm.reload()

        assert vm.get_state().selected_course is None

    def test_changing_workspace_clears_selection_and_rescans(self, vm, tmp_path_factory):
        other = tmp_path_factory.mktemp("other_workspace")
        build_course(other, "ser101_26f_99999")
        vm.select_course(NEW)

        vm.set_workspace_root(str(other))

        state = vm.get_state()
        assert state.selected_course is None
        assert visible(vm) == ["ser101_26f_99999"]
