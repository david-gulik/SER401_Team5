from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from GAVEL.app.dtos.course_summary import AnonymizationStatus, CourseSummary
from GAVEL.app.usecases.list_workspace_courses import (
    ListWorkspaceCoursesRequest,
    ListWorkspaceCoursesUseCase,
)
from GAVEL.app.workspace.layout import CourseKey

_TERM_NAMES = {"s": "Spring", "u": "Summer", "f": "Fall", "w": "Winter"}


class CourseFilter(Enum):
    ALL = "all"
    # Everything that is not up to date, including courses that cannot run yet.
    NOT_UP_TO_DATE = "not_up_to_date"
    UP_TO_DATE = "up_to_date"


def term_label(key: CourseKey) -> str:
    """``Summer 2025 C`` (session letter last, when there is one)."""
    label = f"{_TERM_NAMES[key.term]} {key.year}"
    return f"{label} {key.session.upper()}" if key.session else label


def course_label(key: CourseKey) -> str:
    """``SER 222 (12345)``: course and myASU class number."""
    return f"{key.course_label} ({key.class_number})"


def _matches_filter(course: CourseSummary, course_filter: CourseFilter) -> bool:
    up_to_date = course.status is AnonymizationStatus.UP_TO_DATE
    if course_filter is CourseFilter.UP_TO_DATE:
        return up_to_date
    if course_filter is CourseFilter.NOT_UP_TO_DATE:
        return not up_to_date
    return True


def _matches_search(course: CourseSummary, search: str) -> bool:
    needle = search.strip().lower()
    if not needle:
        return True
    haystack = " ".join(
        [
            course.folder_name,
            course_label(course.key),
            term_label(course.key),
            course.canvas_course_name or "",
        ]
    ).lower()
    return needle in haystack


@dataclass(frozen=True)
class SanitizeUiState:
    """Everything the Sanitize tab needs to paint itself."""

    workspace_root: str = ""
    courses: tuple[CourseSummary, ...] = ()
    course_filter: CourseFilter = CourseFilter.ALL
    course_search: str = ""
    # Folder name of the course the rest of the page works on.
    selected_course: str | None = None
    scan_error: str | None = None

    @property
    def visible_courses(self) -> tuple[CourseSummary, ...]:
        return tuple(
            course
            for course in self.courses
            if _matches_filter(course, self.course_filter)
            and _matches_search(course, self.course_search)
        )

    @property
    def selected_summary(self) -> CourseSummary | None:
        return next(
            (course for course in self.courses if course.folder_name == self.selected_course),
            None,
        )

    def filter_count(self, course_filter: CourseFilter) -> int:
        return sum(1 for course in self.courses if _matches_filter(course, course_filter))


class SanitizeViewModel(QObject):
    state_changed = pyqtSignal(object)  # SanitizeUiState

    def __init__(self, default_workspace_root: Path) -> None:
        super().__init__()
        self._list_courses = ListWorkspaceCoursesUseCase()
        self._state = SanitizeUiState(workspace_root=str(default_workspace_root))

    def get_state(self) -> SanitizeUiState:
        return self._state

    def reload(self) -> None:
        """Scan the workspace again, keeping the selection if that course is still there."""
        root = Path(self._state.workspace_root).expanduser()
        try:
            result = self._list_courses.execute(ListWorkspaceCoursesRequest(workspace_root=root))
        except OSError as exc:
            self._update(
                courses=(), selected_course=None, scan_error=f"Could not read {root}: {exc}"
            )
            return

        folder_names = {course.folder_name for course in result.courses}
        selected = self._state.selected_course
        self._update(
            courses=result.courses,
            selected_course=selected if selected in folder_names else None,
            scan_error=None,
        )

    def set_workspace_root(self, value: str) -> None:
        text = value.strip()
        if not text or text == self._state.workspace_root:
            return
        self._update(workspace_root=text, selected_course=None)
        self.reload()

    def set_course_filter(self, course_filter: CourseFilter) -> None:
        self._update(course_filter=course_filter)

    def set_course_search(self, text: str) -> None:
        self._update(course_search=text)

    def select_course(self, folder_name: str | None) -> None:
        self._update(selected_course=folder_name)

    def _update(self, **changes: object) -> None:
        new_state = replace(self._state, **changes)
        if new_state == self._state:
            return
        self._state = new_state
        self.state_changed.emit(self._state)
