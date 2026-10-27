from __future__ import annotations

from pathlib import Path

from GAVEL.app.workspace.layout import CourseFolder, CourseKey
from GAVEL.app.workspace.manifest import AssignmentEntry
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.analytics.tabs import GenerateReportCard

# Under a workspace, so course.workspace_root resolves; nothing is read from it.
_COURSE = CourseFolder(
    path=Path("workspace") / "courses" / "ser222_25sc_12345",
    key=CourseKey.parse("ser222_25sc_12345"),
)
_RUBRIC_ASSIGNMENT = AssignmentEntry(
    canvas_id=1, name="Module 1 Rubric", module_number=1, has_rubric=True
)


class _RaisingViewModel:
    """A stub view model whose data calls succeed, but whose actions raise an
    exception type that the card's except clauses did not originally list."""

    def list_modules(self, course: CourseFolder) -> tuple[int, ...]:
        return (1,)

    def mapping_names(self) -> tuple[str, ...]:
        return ("ser334_m9",)

    def list_gradebook_columns(self, course: CourseFolder, module_number: int) -> tuple[str, ...]:
        raise RuntimeError("boom")

    def list_rubric_assignments(
        self, course: CourseFolder, module_number: int
    ) -> tuple[AssignmentEntry, ...]:
        return (_RUBRIC_ASSIGNMENT,)

    def generate(self, workspace_root, course, module_number, mapping_name, gradebook_column):
        raise RuntimeError("boom")

    def generate_heat_map(
        self, workspace_root, course, module_number, mapping_name, rubric_assignment
    ):
        raise RuntimeError("boom")


class _RaisingRubricListViewModel(_RaisingViewModel):
    """Like _RaisingViewModel, but listing rubric assignments itself fails."""

    def list_rubric_assignments(
        self, course: CourseFolder, module_number: int
    ) -> tuple[AssignmentEntry, ...]:
        raise RuntimeError("boom")


class _RaisingModulesViewModel(_RaisingViewModel):
    """Like _RaisingViewModel, but listing modules itself fails."""

    def list_modules(self, course: CourseFolder) -> tuple[int, ...]:
        raise RuntimeError("boom")


def _modules(card: GenerateReportCard) -> list[str]:
    return [card._module_box.itemText(i) for i in range(card._module_box.count())]


def _card(theme, view_model=None) -> GenerateReportCard:
    card = GenerateReportCard(theme, build_dataset_readers(), view_model or _RaisingViewModel())
    card.set_course(_COURSE)
    return card


def test_card_waits_for_a_course(qapp, theme):
    card = GenerateReportCard(theme, build_dataset_readers(), _RaisingViewModel())

    assert _modules(card) == []
    assert card._status.text() == "No course selected."


def test_set_course_lists_the_modules_of_that_course(qapp, theme):
    card = _card(theme)

    assert card._selected_course() == _COURSE
    assert _modules(card) == ["1"]


def test_clearing_the_course_empties_the_modules(qapp, theme):
    card = _card(theme)

    card.set_course(None)

    assert _modules(card) == []
    assert card._status.text() == "No course selected."


def test_refresh_modules_reports_an_unexpected_exception_without_crashing(qapp, theme):
    card = GenerateReportCard(theme, build_dataset_readers(), _RaisingModulesViewModel())

    card.set_course(_COURSE)

    assert "Could not read the workspace" in card._status.text()
    assert "boom" in card._status.text()


def test_refresh_columns_reports_an_unexpected_exception_without_crashing(qapp, theme):
    card = _card(theme)

    card._refresh_columns()

    assert "Could not read the gradebook" in card._status.text()
    assert "boom" in card._status.text()


def test_refresh_rubric_assignments_reports_an_unexpected_exception_without_crashing(qapp, theme):
    card = _card(theme, _RaisingRubricListViewModel())

    card._refresh_rubric_assignments()

    assert "Could not read the manifest" in card._status.text()
    assert "boom" in card._status.text()


def test_generate_signed_error_report_reports_an_unexpected_exception_without_crashing(qapp, theme):
    card = _card(theme)
    card._report_type_box.setCurrentText(GenerateReportCard._SIGNED_ERROR)
    card._column_box.addItem("some_column")

    card._generate()

    assert "Could not generate the report" in card._status.text()
    assert "boom" in card._status.text()


def test_generate_heat_map_report_reports_an_unexpected_exception_without_crashing(qapp, theme):
    card = _card(theme)
    card._report_type_box.setCurrentText(GenerateReportCard._HEAT_MAP)
    card._refresh_rubric_assignments()

    card._generate()

    assert "Could not generate the report" in card._status.text()
    assert "boom" in card._status.text()
