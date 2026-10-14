from __future__ import annotations

from pathlib import Path

from GAVEL.app.workspace.layout import CourseFolder, CourseKey
from GAVEL.bootstrap import build_dataset_readers
from GAVEL.pages.analytics.tabs import GenerateReportCard

_COURSE = CourseFolder(path=Path("unused"), key=CourseKey.parse("ser222_25sc_12345"))


class _RaisingViewModel:
    """A stub view model whose data calls succeed, but whose actions raise an
    exception type that the card's except clauses did not originally list."""

    def list_courses(self, workspace_root: Path) -> tuple[CourseFolder, ...]:
        return (_COURSE,)

    def list_modules(self, course: CourseFolder) -> tuple[int, ...]:
        return (1,)

    def mapping_names(self) -> tuple[str, ...]:
        return ("ser334_m9",)

    def list_gradebook_columns(self, course: CourseFolder, module_number: int) -> tuple[str, ...]:
        raise RuntimeError("boom")

    def generate(self, workspace_root, course, module_number, mapping_name, gradebook_column):
        raise RuntimeError("boom")


def _card(theme, tmp_path: Path) -> GenerateReportCard:
    card = GenerateReportCard(theme, build_dataset_readers(), tmp_path, _RaisingViewModel())
    card._refresh_courses()
    card._refresh_modules()
    return card


def test_refresh_columns_reports_an_unexpected_exception_without_crashing(qapp, theme, tmp_path):
    card = _card(theme, tmp_path)

    card._refresh_columns()

    assert "Could not read the gradebook" in card._status.text()
    assert "boom" in card._status.text()


def test_generate_reports_an_unexpected_exception_without_crashing(qapp, theme, tmp_path):
    card = _card(theme, tmp_path)
    card._column_box.addItem("some_column")

    card._generate()

    assert "Could not generate the report" in card._status.text()
    assert "boom" in card._status.text()
