from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.course_summary import AnonymizationStatus
from GAVEL.core.background import run_now
from GAVEL.core.status import Status
from GAVEL.pages.sanitize.tabs import SanitizeTab
from GAVEL.pages.sanitize.viewmodel import RunState, SanitizeViewModel, page_status
from tests.pages.sanitize.course_folders import (
    ANONYMIZED,
    EVERY_OUTCOME,
    build_course,
    write_students,
)

NEW = "ser222_26f_11111"
DONE = "ser222_26f_22222"
NO_FORM = "ser334_26u_44444"
NOBODY = "ser340_26f_55555"


class HeldRunner:
    """Starts nothing until the test says so, to look at the page mid-run."""

    def __init__(self) -> None:
        self.pending = None

    def __call__(self, fn, on_result, on_error) -> None:
        self.pending = (fn, on_result, on_error)

    def finish(self) -> None:
        fn, on_result, on_error = self.pending
        self.pending = None
        run_now(fn, on_result, on_error)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    write_students(build_course(tmp_path, NEW, rubric_assessments=2), EVERY_OUTCOME)
    build_course(tmp_path, DONE, anonymized_at=ANONYMIZED)
    build_course(tmp_path, NO_FORM, consent_form=False)
    build_course(tmp_path, NOBODY, students=3, consented=0)
    return tmp_path


def make_vm(workspace: Path, runner=run_now) -> SanitizeViewModel:
    vm = SanitizeViewModel(default_workspace_root=workspace, runner=runner)
    vm.reload()
    return vm


@pytest.fixture
def vm(qapp, workspace) -> SanitizeViewModel:
    return make_vm(workspace)


class Page:
    """A SanitizeTab with the dialogs and file manager replaced by recorders."""

    def __init__(self, theme, vm, confirm_answer: bool = True) -> None:
        self.opened: list[Path] = []
        self.asked: list[str] = []

        def confirm(_parent, text: str) -> bool:
            self.asked.append(text)
            return confirm_answer

        self.tab = SanitizeTab(theme, vm, open_location=self.opened.append, confirm_replace=confirm)
        self.card = self.tab.anonymize_card


@pytest.fixture
def page(qapp, theme, vm):
    page = Page(theme, vm)
    yield page
    page.tab.deleteLater()


class TestRunButton:
    def test_disabled_until_a_course_is_selected(self, page):
        assert not page.card.run_button.isEnabled()
        assert page.card.run_button.text() == "Select a course to anonymize"

    def test_counts_the_students_who_will_be_kept(self, page, vm):
        vm.select_course(NEW)

        assert page.card.run_button.isEnabled()
        assert page.card.run_button.text() == "Anonymize 2 consenting students"

    def test_says_re_anonymize_for_a_course_done_before(self, page, vm):
        vm.select_course(DONE)

        assert page.card.run_button.text() == "Re-anonymize 3 consenting students"

    @pytest.mark.parametrize(
        ("course", "reason"),
        [(NO_FORM, "Needs a consent form"), (NOBODY, "No students consented")],
    )
    def test_disabled_with_the_reason(self, page, vm, course, reason):
        vm.select_course(course)

        assert not page.card.run_button.isEnabled()
        assert page.card.run_button.text() == reason


class TestRunning:
    def test_first_run_needs_no_confirmation(self, page, vm):
        vm.select_course(NEW)

        page.card.run_button.click()

        assert page.asked == []
        assert vm.get_state().run_state is RunState.SUCCEEDED

    def test_run_writes_anonymized_files_and_refreshes_the_course(self, page, vm, workspace):
        vm.select_course(NEW)

        page.card.run_button.click()

        assert (workspace / "courses" / NEW / "anonymized" / "consent_form.csv").is_file()
        assert vm.get_state().selected_summary.status is AnonymizationStatus.UP_TO_DATE

    def test_results_list_each_file(self, page, vm):
        vm.select_course(NEW)

        page.card.run_button.click()

        rows = page.card.result_texts()
        assert rows[0] == ["FILE", "KEPT", "REMOVED", "NOTE"]
        assert [row[0] for row in rows[1:]] == [
            "Consent form",
            "Roster",
            "Gradebook",
            "Rubric assessments",
        ]
        assert rows[2][1:3] == ["2", "5"]

    def test_rerun_asks_first_and_cancel_does_nothing(self, qapp, theme, vm, workspace):
        page = Page(theme, vm, confirm_answer=False)
        vm.select_course(DONE)
        stale = workspace / "courses" / DONE / "anonymized" / "roster.csv"

        page.card.run_button.click()

        assert "already anonymized" in page.asked[0]
        assert vm.get_state().run_state is RunState.IDLE
        assert stale.is_file()
        page.tab.deleteLater()

    def test_confirmed_rerun_replaces_the_anonymized_folder(self, page, vm, workspace):
        leftover = workspace / "courses" / DONE / "anonymized" / "assignments" / "old.json"
        leftover.parent.mkdir(parents=True)
        leftover.write_text("[]", encoding="utf-8")
        vm.select_course(DONE)

        page.card.run_button.click()

        assert page.asked
        assert vm.get_state().run_state is RunState.SUCCEEDED
        assert not leftover.exists()

    def test_failure_is_reported(self, page, vm, workspace):
        vm.select_course(NEW)
        (workspace / "courses" / NEW / "original" / "consent_form.csv").unlink()

        page.card.run_button.click()

        state = vm.get_state()
        assert state.run_state is RunState.FAILED
        assert "Consent form is missing" in state.run_error
        assert "failed" in page.card.results_status.text()


class TestWhileRunning:
    @pytest.fixture
    def held(self, qapp, theme, workspace):
        runner = HeldRunner()
        vm = make_vm(workspace, runner)
        page = Page(theme, vm)
        vm.select_course(NEW)
        page.card.run_button.click()
        yield runner, vm, page
        page.tab.deleteLater()

    def test_busy_bar_and_locked_course_choice(self, held):
        _, vm, page = held

        assert vm.get_state().is_running
        assert page.tab.busy_bar.isVisibleTo(page.tab)
        assert not page.tab.course_tree.isEnabled()
        assert not page.card.run_button.isEnabled()
        assert page.card.run_button.text() == "Anonymizing…"

    def test_selection_cannot_change_mid_run(self, held):
        _, vm, _ = held

        vm.select_course(DONE)

        assert vm.get_state().selected_course == NEW

    def test_everything_unlocks_when_it_finishes(self, held):
        runner, vm, page = held

        runner.finish()

        assert not vm.get_state().is_running
        assert not page.tab.busy_bar.isVisibleTo(page.tab)
        assert page.tab.course_tree.isEnabled()


class TestOpenFolder:
    def test_disabled_until_anonymized_exists(self, page, vm):
        vm.select_course(NEW)

        assert not page.card.open_button.isEnabled()

    def test_opens_the_anonymized_folder(self, page, vm, workspace):
        vm.select_course(DONE)

        page.card.open_button.click()

        assert page.opened == [workspace / "courses" / DONE / "anonymized"]


class TestStatusCard:
    def test_asks_for_a_course_first(self, vm):
        assert page_status(vm.get_state())[0] is Status.UNKNOWN

    def test_ready_message(self, vm):
        vm.select_course(NEW)

        status, message, _ = page_status(vm.get_state())

        assert status is Status.NOMINAL
        assert message == "Ready. 2 of 7 students in SER 222 (11111) will be included."

    def test_missing_consent_form_is_critical(self, vm):
        vm.select_course(NO_FORM)

        assert page_status(vm.get_state())[0] is Status.CRITICAL

    def test_after_a_run_names_where_it_was_saved(self, page, vm, workspace):
        vm.select_course(NEW)
        page.card.run_button.click()

        output = str(workspace / "courses" / NEW / "anonymized")
        assert page.tab.status_message.text() == f"Anonymized 2 students to {output}"
        assert page.tab.last_saved.text() == output

    def test_failed_run_is_critical(self, page, vm, workspace):
        vm.select_course(NEW)
        (workspace / "courses" / NEW / "original" / "consent_form.csv").unlink()
        page.card.run_button.click()

        assert page_status(vm.get_state())[0] is Status.CRITICAL
