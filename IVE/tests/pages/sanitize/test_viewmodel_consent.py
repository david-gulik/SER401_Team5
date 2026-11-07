from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.consent_decision import ConsentStatus
from GAVEL.app.dtos.course_summary import AnonymizationStatus
from GAVEL.core.background import run_now
from GAVEL.core.status import Status
from GAVEL.pages.sanitize.tabs import banner_text
from GAVEL.pages.sanitize.viewmodel import (
    ConsentFilter,
    RunState,
    SanitizeViewModel,
    page_status,
)
from tests.pages.sanitize.course_folders import (
    EVERY_OUTCOME,
    build_course,
    sis_id,
    write_students,
)

REVIEWED = "ser222_26f_11111"
SIMPLE = "ser222_26f_22222"
NO_FORM = "ser334_26u_44444"


@pytest.fixture
def vm(qapp, tmp_path: Path) -> SanitizeViewModel:
    write_students(build_course(tmp_path, REVIEWED), EVERY_OUTCOME)
    build_course(tmp_path, SIMPLE, students=3, consented=3)
    build_course(tmp_path, NO_FORM, consent_form=False)
    vm = SanitizeViewModel(default_workspace_root=tmp_path)
    vm.reload()
    return vm


def names(vm: SanitizeViewModel) -> list[str]:
    return [decision.name for decision in vm.get_state().visible_decisions]


class TestLoading:
    def test_nothing_to_review_until_a_course_is_selected(self, vm):
        state = vm.get_state()

        assert state.consent_decisions == ()
        assert not state.consent_form_found

    def test_selecting_a_course_loads_its_decisions(self, vm):
        vm.select_course(REVIEWED)

        state = vm.get_state()
        assert state.consent_form_found
        assert len(state.consent_decisions) == len(EVERY_OUTCOME)

    def test_course_without_a_consent_form(self, vm):
        vm.select_course(NO_FORM)

        state = vm.get_state()
        assert not state.consent_form_found
        assert state.consent_error is None
        assert state.consent_decisions == ()

    def test_unreadable_consent_form_sets_an_error(self, vm, tmp_path):
        form = tmp_path / "courses" / REVIEWED / "original" / "consent_form.csv"
        form.write_text("nonsense\n", encoding="utf-8")

        vm.select_course(REVIEWED)

        state = vm.get_state()
        assert state.consent_error and "Could not read" in state.consent_error
        assert state.consent_decisions == ()

    def test_reload_rereads_the_selected_course(self, vm, tmp_path):
        vm.select_course(SIMPLE)
        write_students(tmp_path / "courses" / SIMPLE, EVERY_OUTCOME)

        vm.reload()

        assert len(vm.get_state().consent_decisions) == len(EVERY_OUTCOME)

    def test_deselecting_clears_the_review(self, vm):
        vm.select_course(REVIEWED)

        vm.select_course(None)

        assert vm.get_state().consent_decisions == ()


class TestFiltering:
    @pytest.fixture(autouse=True)
    def selected(self, vm):
        vm.select_course(REVIEWED)

    def test_counts_per_filter(self, vm):
        state = vm.get_state()

        assert state.consent_count(ConsentFilter.ALL) == 7
        assert state.consent_count(ConsentFilter.INCLUDED) == 2
        assert state.consent_count(ConsentFilter.EXCLUDED) == 5
        assert state.consent_count(ConsentFilter.DECLINED) == 1
        assert state.consent_count(ConsentFilter.NAME_PROBLEM) == 3
        assert state.consent_count(ConsentFilter.NO_RESPONSE) == 1

    def test_name_problem_covers_blank_typo_and_mismatch(self, vm):
        vm.set_consent_filter(ConsentFilter.NAME_PROBLEM)

        statuses = {d.status for d in vm.get_state().visible_decisions}

        assert statuses == {
            ConsentStatus.NAME_BLANK,
            ConsentStatus.POSSIBLE_TYPO,
            ConsentStatus.NAME_MISMATCH,
        }

    def test_toggling_a_tile_twice_shows_everyone_again(self, vm):
        vm.toggle_consent_filter(ConsentFilter.DECLINED)
        assert names(vm) == ["Hannah Fischer"]

        vm.toggle_consent_filter(ConsentFilter.DECLINED)

        assert vm.get_state().consent_filter is ConsentFilter.ALL

    @pytest.mark.parametrize(
        ("search", "expected"),
        [("okafor", ["Chinedu Okafor"]), ("1220440004", ["Omar Haddad"]), ("zzz", [])],
    )
    def test_search_by_name_or_sis_id(self, vm, search, expected):
        vm.set_consent_search(search)

        assert names(vm) == expected

    def test_switching_course_resets_filter_and_search(self, vm):
        vm.set_consent_filter(ConsentFilter.EXCLUDED)
        vm.set_consent_search("okafor")

        vm.select_course(SIMPLE)

        state = vm.get_state()
        assert state.consent_filter is ConsentFilter.ALL
        assert state.consent_search == ""


KENJI = sis_id(5)  # possible typo in EVERY_OUTCOME
LUCA = sis_id(2)  # name blank


class TestOverrides:
    @pytest.fixture
    def anonymized_vm(self, qapp, tmp_path: Path) -> SanitizeViewModel:
        """REVIEWED anonymized once, with no overrides, so it starts up to date."""
        write_students(build_course(tmp_path, REVIEWED), EVERY_OUTCOME)
        vm = SanitizeViewModel(default_workspace_root=tmp_path, runner=run_now)
        vm.reload()
        vm.select_course(REVIEWED)
        vm.anonymize()
        return vm

    def test_override_includes_the_student(self, vm):
        vm.select_course(REVIEWED)

        vm.override_consent(KENJI)

        state = vm.get_state()
        assert state.overridden_count == 1
        assert state.included_count == 3
        assert state.consent_count(ConsentFilter.NAME_PROBLEM) == 2
        assert state.override_error is None

    def test_refused_override_sets_an_error_and_changes_nothing(self, vm):
        vm.select_course(REVIEWED)

        vm.override_consent(LUCA)

        state = vm.get_state()
        assert "Only a possible typo or a name mismatch" in state.override_error
        assert state.overridden_count == 0
        assert state.consent_error is None

    def test_switching_course_clears_an_override_error(self, vm):
        vm.select_course(REVIEWED)
        vm.override_consent(LUCA)

        vm.select_course(SIMPLE)

        assert vm.get_state().override_error is None

    def test_nothing_happens_without_a_selected_course(self, vm, tmp_path):
        vm.override_consent(KENJI)

        assert not (tmp_path / "courses" / REVIEWED / "manifest.json").exists()

    def test_override_marks_an_anonymized_course_out_of_date(self, anonymized_vm):
        assert anonymized_vm.get_state().selected_summary.status is AnonymizationStatus.UP_TO_DATE

        anonymized_vm.override_consent(KENJI)

        state = anonymized_vm.get_state()
        course = state.selected_summary
        assert course.status is AnonymizationStatus.OUT_OF_DATE
        status, message, _ = page_status(state)
        assert status is Status.CAUTION
        assert message.startswith("Consent overrides changed after the last run.")
        assert banner_text(course).startswith("Out of date: consent overrides changed after")

    def test_override_clears_the_finished_run(self, anonymized_vm):
        assert anonymized_vm.get_state().selected_run_state is RunState.SUCCEEDED

        anonymized_vm.override_consent(KENJI)

        state = anonymized_vm.get_state()
        assert state.selected_run_state is RunState.IDLE
        assert state.run_result is None
