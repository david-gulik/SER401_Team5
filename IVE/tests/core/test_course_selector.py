from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QLabel

from GAVEL.app.workspace.layout import Workspace
from GAVEL.core.active_course import ActiveCourse
from GAVEL.core.background import run_now
from GAVEL.core.course_selector import (
    NO_COURSE_TEXT,
    ActiveCourseChip,
    ActiveCourseGate,
    ChooseCourseCard,
    CoursePickerPopup,
)
from tests.pages.sanitize.course_folders import ANONYMIZED, build_course

READY = "ser222_26f_11111"
STALE = "ser240_26f_22222"
FRESH = "ser316_26s_33333"
BLOCKED = "ser334_26u_44444"


def active(tmp_path: Path) -> ActiveCourse:
    settings = QSettings(str(tmp_path / "gavel.ini"), QSettings.Format.IniFormat)
    return ActiveCourse(Workspace(tmp_path), settings)


def course_dirs(tmp_path: Path, *names: str) -> None:
    for name in names:
        (tmp_path / "courses" / name).mkdir(parents=True)


def popup_for(theme, tmp_path: Path, active_course: ActiveCourse | None = None):
    popup = CoursePickerPopup(theme, active_course or active(tmp_path), runner=run_now)
    popup.reload()
    return popup


def folder_names(popup: CoursePickerPopup) -> list[str]:
    items = (popup.list_widget.item(i) for i in range(popup.list_widget.count()))
    return [item.data(Qt.ItemDataRole.UserRole) for item in items]


def enabled(popup: CoursePickerPopup) -> list[bool]:
    items = (popup.list_widget.item(i) for i in range(popup.list_widget.count()))
    return [bool(item.flags() & Qt.ItemFlag.ItemIsEnabled) for item in items]


class _UnreadableWorkspace:
    def execute(self, request):
        raise OSError("locked")


# --- picker popup ---------------------------------------------------------


def test_popup_lists_every_course_with_its_status(qapp, theme, tmp_path):
    build_course(tmp_path, READY, anonymized_at=ANONYMIZED, canvas_course_name="SER 222 Fall")
    build_course(tmp_path, FRESH)

    popup = popup_for(theme, tmp_path)

    assert folder_names(popup) == [READY, FRESH]
    assert popup.row(0).status_label.text() == "●  Up to date"
    assert popup.row(0).canvas_label.text() == "SER 222 Fall"
    assert popup.row(1).status_label.text() == "●  Not anonymized"
    assert popup.footer_label.text() == "2 courses in the workspace, 1 anonymized"
    assert popup.footer_label.toolTip() == str(tmp_path / "courses")


def test_only_courses_with_an_anonymized_copy_can_be_picked(qapp, theme, tmp_path):
    build_course(tmp_path, READY, anonymized_at=ANONYMIZED)
    stale = build_course(tmp_path, STALE, anonymized_at=ANONYMIZED)
    (stale / "original" / "roster.csv").write_text("changed", encoding="utf-8")
    build_course(tmp_path, FRESH)
    build_course(tmp_path, BLOCKED, consent_form=False)

    popup = popup_for(theme, tmp_path)

    assert folder_names(popup) == [READY, STALE, FRESH, BLOCKED]
    assert enabled(popup) == [True, True, False, False]
    assert popup.row(2).status_label.text() == "●  Not anonymized"
    assert popup.row(3).status_label.text() == "●  No consent form"
    assert "Sanitize page" in popup.list_widget.item(2).toolTip()
    assert "consent form" in popup.list_widget.item(3).toolTip()


def test_clicking_a_course_that_cannot_be_picked_changes_nothing(qapp, theme, tmp_path):
    build_course(tmp_path, FRESH)
    active_course = active(tmp_path)
    popup = popup_for(theme, tmp_path, active_course)

    popup.list_widget.itemClicked.emit(popup.list_widget.item(0))

    assert active_course.course is None


def test_popup_highlights_the_active_course(qapp, theme, tmp_path):
    build_course(tmp_path, READY, anonymized_at=ANONYMIZED)
    build_course(tmp_path, FRESH, anonymized_at=ANONYMIZED)
    active_course = active(tmp_path)
    active_course.select(active_course.workspace.list_courses()[1])

    popup = popup_for(theme, tmp_path, active_course)

    assert popup.list_widget.currentRow() == 1


def test_picking_a_row_makes_that_course_active_and_closes_the_popup(qapp, theme, tmp_path):
    build_course(tmp_path, READY, anonymized_at=ANONYMIZED)
    build_course(tmp_path, FRESH, anonymized_at=ANONYMIZED)
    active_course = active(tmp_path)
    popup = CoursePickerPopup(theme, active_course, runner=run_now)
    popup.show()
    popup.reload()
    assert popup.isVisible()

    popup.list_widget.itemClicked.emit(popup.list_widget.item(1))

    assert active_course.course is not None
    assert active_course.course.key.folder_name == FRESH
    assert active_course.course.path == tmp_path / "courses" / FRESH
    assert popup.isHidden()


def test_loading_rows_with_canvas_names_keeps_an_open_popup_open(qapp, theme, tmp_path):
    # Showing any plain window closes every active popup, so no row may open one while
    # it is built (a parentless label with setVisible(True) once did).
    build_course(tmp_path, READY, canvas_course_name="SER 222 Fall")
    build_course(tmp_path, FRESH)
    popup = CoursePickerPopup(theme, active(tmp_path), runner=run_now)
    popup.show()
    assert qapp.activePopupWidget() is popup

    popup.reload()

    assert popup.isVisible()
    assert qapp.activePopupWidget() is popup
    popup.hide()


def test_filter_hides_courses_that_do_not_match(qapp, theme, tmp_path):
    build_course(tmp_path, READY, canvas_course_name="Data Structures")
    build_course(tmp_path, FRESH)
    popup = popup_for(theme, tmp_path)

    popup.search_input.setText("316")
    assert [popup.list_widget.item(i).isHidden() for i in range(2)] == [True, False]

    popup.search_input.setText("structures")
    assert [popup.list_widget.item(i).isHidden() for i in range(2)] == [False, True]

    popup.search_input.setText("")
    assert [popup.list_widget.item(i).isHidden() for i in range(2)] == [False, False]


def test_popup_says_when_the_workspace_has_no_courses(qapp, theme, tmp_path):
    popup = popup_for(theme, tmp_path)

    assert popup.list_widget.count() == 0
    assert popup.footer_label.text().startswith("No courses in ")


def test_popup_reports_a_workspace_it_cannot_read(qapp, theme, tmp_path):
    popup = CoursePickerPopup(
        theme, active(tmp_path), list_courses=_UnreadableWorkspace(), runner=run_now
    )

    popup.reload()

    assert popup.list_widget.count() == 0
    assert popup.footer_label.text() == "Could not read the workspace: locked"


# --- status-bar chip ------------------------------------------------------


def test_chip_follows_the_active_course(qapp, theme, tmp_path):
    course_dirs(tmp_path, READY)
    active_course = active(tmp_path)
    chip = ActiveCourseChip(theme, active_course)
    assert chip.name_label.text() == NO_COURSE_TEXT

    active_course.select(active_course.workspace.list_courses()[0])
    assert chip.name_label.text() == READY

    active_course.select(None)
    assert chip.name_label.text() == NO_COURSE_TEXT


# --- choose-a-course card and gate ----------------------------------------


def test_card_button_opens_the_shared_picker(qapp, theme, tmp_path):
    build_course(tmp_path, READY, anonymized_at=ANONYMIZED)
    popup = CoursePickerPopup(theme, active(tmp_path), runner=run_now)
    card = ChooseCourseCard(theme, "Inspect Grades", popup)
    card.show()
    assert popup.isHidden()

    card.choose_button.click()

    assert popup.isVisible()
    assert folder_names(popup) == [READY]
    popup.hide()
    card.hide()


def test_gate_shows_the_card_until_a_course_is_active(qapp, theme, tmp_path):
    course_dirs(tmp_path, READY)
    active_course = active(tmp_path)
    popup = CoursePickerPopup(theme, active_course, runner=run_now)
    page = QLabel("page")
    gate = ActiveCourseGate(theme, active_course, "Analytics", page, popup)
    assert gate.currentWidget() is gate.card

    active_course.select(active_course.workspace.list_courses()[0])
    assert gate.currentWidget() is page

    active_course.select(None)
    assert gate.currentWidget() is gate.card


def test_gate_starts_on_the_page_when_a_course_is_already_active(qapp, theme, tmp_path):
    course_dirs(tmp_path, READY)
    active_course = active(tmp_path)
    active_course.select(active_course.workspace.list_courses()[0])
    popup = CoursePickerPopup(theme, active_course, runner=run_now)
    page = QLabel("page")

    gate = ActiveCourseGate(theme, active_course, "Analytics", page, popup)

    assert gate.currentWidget() is page
