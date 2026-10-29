from __future__ import annotations

from pathlib import Path

from GAVEL.app.workspace.layout import CourseFolder, CourseKey
from GAVEL.app.workspace.manifest import AssignmentEntry
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.analytics.tabs import GenerateReportCard

_COURSE = CourseFolder(path=Path("unused"), key=CourseKey.parse("ser222_25sc_12345"))
_RUBRIC_ASSIGNMENT = AssignmentEntry(
    canvas_id=1, name="Module 1 Rubric", module_number=1, has_rubric=True
)


class _RaisingViewModel:
    """A stub view model whose data calls succeed, but whose actions raise an
    exception type that the card's except clauses did not originally list."""

    def list_courses(self, workspace_root: Path) -> tuple[CourseFolder, ...]:
        return (_COURSE,)

    def list_modules(self, course: CourseFolder) -> tuple[int, ...]:
        return (1,)

    def resolve_mapping_name(self, course: CourseFolder, module_number: int) -> str | None:
        return "ser334_m9"

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


class _RaisingCoursesViewModel(_RaisingViewModel):
    """Like _RaisingViewModel, but listing courses itself fails."""

    def list_courses(self, workspace_root: Path) -> tuple[CourseFolder, ...]:
        raise RuntimeError("boom")


class _RaisingModulesViewModel(_RaisingViewModel):
    """Like _RaisingViewModel, but listing modules itself fails."""

    def list_modules(self, course: CourseFolder) -> tuple[int, ...]:
        raise RuntimeError("boom")


def _card(theme, tmp_path: Path, view_model=None) -> GenerateReportCard:
    card = GenerateReportCard(
        theme, build_dataset_readers(), tmp_path, view_model or _RaisingViewModel()
    )
    card._refresh_courses()
    card._refresh_modules()
    return card


def test_refresh_courses_reports_an_unexpected_exception_without_crashing(qapp, theme, tmp_path):
    card = GenerateReportCard(theme, build_dataset_readers(), tmp_path, _RaisingCoursesViewModel())

    card._refresh_courses()

    assert "Could not read the workspace" in card._status.text()
    assert "boom" in card._status.text()


def test_refresh_modules_reports_an_unexpected_exception_without_crashing(qapp, theme, tmp_path):
    card = GenerateReportCard(theme, build_dataset_readers(), tmp_path, _RaisingModulesViewModel())

    card._refresh_modules()

    assert "Could not read the workspace" in card._status.text()
    assert "boom" in card._status.text()


def test_refresh_columns_reports_an_unexpected_exception_without_crashing(qapp, theme, tmp_path):
    card = _card(theme, tmp_path)

    card._refresh_columns()

    assert "Could not read the gradebook" in card._status.text()
    assert "boom" in card._status.text()


def test_refresh_rubric_assignments_reports_an_unexpected_exception_without_crashing(
    qapp, theme, tmp_path
):
    card = _card(theme, tmp_path, _RaisingRubricListViewModel())

    card._refresh_rubric_assignments()

    assert "Could not read the manifest" in card._status.text()
    assert "boom" in card._status.text()


def test_generate_signed_error_report_reports_an_unexpected_exception_without_crashing(
    qapp, theme, tmp_path
):
    card = _card(theme, tmp_path)
    card._report_type_box.setCurrentText(GenerateReportCard._SIGNED_ERROR)
    card._column_box.addItem("some_column")

    card._generate()

    assert "Could not generate the report" in card._status.text()
    assert "boom" in card._status.text()


def test_generate_heat_map_report_reports_an_unexpected_exception_without_crashing(
    qapp, theme, tmp_path
):
    card = _card(theme, tmp_path)
    card._report_type_box.setCurrentText(GenerateReportCard._HEAT_MAP)
    card._refresh_rubric_assignments()

    card._generate()

    assert "Could not generate the report" in card._status.text()
    assert "boom" in card._status.text()
