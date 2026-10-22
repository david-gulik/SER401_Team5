from __future__ import annotations

from pathlib import Path

from GAVEL.app.workspace.layout import CourseFolder, CourseKey
from GAVEL.pages.analytics.tabs import GenerateReportCard

_COURSE = CourseFolder(
    path=Path("courses/ser222_25sc_12345"),
    key=CourseKey("SER", "222", 2025, "s", "c", "12345"),
)


class _RaisingViewModel:
    def list_courses(self, workspace_root: Path):
        return (_COURSE,)

    def list_modules(self, course):
        return (9,)

    def mapping_names(self):
        return ("ser334_m9",)

    def list_gradebook_columns(self, course, module_number):
        raise ValueError("gradebook boom")

    def list_rubric_assignments(self, course, module_number):
        raise ValueError("rubric boom")

    def generate(self, *args, **kwargs):
        raise ValueError("generate boom")


def test_a_bad_manifest_when_listing_rubric_assignments_is_reported_without_crashing(
    qapp, theme, tmp_path: Path
) -> None:
    card = GenerateReportCard(
        theme,
        dataset_readers=None,
        workspace_root=tmp_path,
        view_model=_RaisingViewModel(),
    )

    card._refresh_rubric_assignments()

    assert "rubric boom" in card._status.text()
