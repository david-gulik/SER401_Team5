from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from GAVEL.app.dtos.consent_decision import ConsentDecision, ConsentStatus
from GAVEL.app.dtos.course_summary import AnonymizationStatus, CourseSummary
from GAVEL.app.usecases.list_workspace_courses import (
    ListWorkspaceCoursesRequest,
    ListWorkspaceCoursesUseCase,
)
from GAVEL.app.usecases.review_course_consent import (
    CONSENT_READ_ERRORS,
    ReviewCourseConsentRequest,
    ReviewCourseConsentUseCase,
)
from GAVEL.app.workspace.layout import CourseKey

_TERM_NAMES = {"s": "Spring", "u": "Summer", "f": "Fall", "w": "Winter"}


class CourseFilter(Enum):
    ALL = "all"
    # Everything that is not up to date, including courses that cannot run yet.
    NOT_UP_TO_DATE = "not_up_to_date"
    UP_TO_DATE = "up_to_date"


class ConsentFilter(Enum):
    """Which students the Consent Review table shows.

    ALL, INCLUDED and EXCLUDED are the segmented control; the rest are the
    summary tiles, each a slice of EXCLUDED.
    """

    ALL = "all"
    INCLUDED = "included"
    EXCLUDED = "excluded"
    DECLINED = "declined"
    NAME_PROBLEM = "name_problem"
    NO_RESPONSE = "no_response"


# Statuses where the student said yes but the typed name did not check out.
NAME_PROBLEM_STATUSES = frozenset(
    {ConsentStatus.NAME_BLANK, ConsentStatus.POSSIBLE_TYPO, ConsentStatus.NAME_MISMATCH}
)
_FILTER_STATUSES = {
    ConsentFilter.INCLUDED: frozenset({ConsentStatus.INCLUDED}),
    ConsentFilter.EXCLUDED: frozenset(ConsentStatus) - {ConsentStatus.INCLUDED},
    ConsentFilter.DECLINED: frozenset({ConsentStatus.DECLINED}),
    ConsentFilter.NAME_PROBLEM: NAME_PROBLEM_STATUSES,
    ConsentFilter.NO_RESPONSE: frozenset({ConsentStatus.NO_RESPONSE}),
}


def matches_consent_filter(decision: ConsentDecision, consent_filter: ConsentFilter) -> bool:
    if consent_filter is ConsentFilter.ALL:
        return True
    return decision.status in _FILTER_STATUSES[consent_filter]


def _matches_consent_search(decision: ConsentDecision, search: str) -> bool:
    needle = search.strip().lower()
    return not needle or needle in decision.name.lower() or needle in str(decision.sis_id)


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

    # Consent Review, for the selected course.
    consent_decisions: tuple[ConsentDecision, ...] = ()
    consent_form_found: bool = False
    consent_error: str | None = None
    consent_filter: ConsentFilter = ConsentFilter.ALL
    consent_search: str = ""

    @property
    def visible_decisions(self) -> tuple[ConsentDecision, ...]:
        return tuple(
            decision
            for decision in self.consent_decisions
            if matches_consent_filter(decision, self.consent_filter)
            and _matches_consent_search(decision, self.consent_search)
        )

    def consent_count(self, consent_filter: ConsentFilter) -> int:
        return sum(
            1
            for decision in self.consent_decisions
            if matches_consent_filter(decision, consent_filter)
        )

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
        self._review_consent = ReviewCourseConsentUseCase()
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
            **self._consent_fields(selected if selected in folder_names else None, result.courses),
        )

    def set_workspace_root(self, value: str) -> None:
        text = value.strip()
        if not text or text == self._state.workspace_root:
            return
        self._update(workspace_root=text, selected_course=None, **self._consent_fields(None, ()))
        self.reload()

    def set_course_filter(self, course_filter: CourseFilter) -> None:
        self._update(course_filter=course_filter)

    def set_course_search(self, text: str) -> None:
        self._update(course_search=text)

    def select_course(self, folder_name: str | None) -> None:
        if folder_name == self._state.selected_course:
            return
        self._update(
            selected_course=folder_name,
            consent_filter=ConsentFilter.ALL,
            consent_search="",
            **self._consent_fields(folder_name, self._state.courses),
        )

    def set_consent_filter(self, consent_filter: ConsentFilter) -> None:
        self._update(consent_filter=consent_filter)

    def toggle_consent_filter(self, consent_filter: ConsentFilter) -> None:
        """A tile click: filter to that slice, or back to everyone if it is already on."""
        if self._state.consent_filter is consent_filter:
            consent_filter = ConsentFilter.ALL
        self._update(consent_filter=consent_filter)

    def set_consent_search(self, text: str) -> None:
        self._update(consent_search=text)

    def _consent_fields(
        self, folder_name: str | None, courses: tuple[CourseSummary, ...]
    ) -> dict[str, object]:
        """Consent Review state for a course, read fresh from its folder."""
        course = next((c for c in courses if c.folder_name == folder_name), None)
        empty: dict[str, object] = {
            "consent_decisions": (),
            "consent_form_found": False,
            "consent_error": None,
        }
        if course is None:
            return empty
        try:
            review = self._review_consent.execute(ReviewCourseConsentRequest(course.path))
        except CONSENT_READ_ERRORS as exc:
            return {
                **empty,
                "consent_form_found": True,
                "consent_error": f"Could not read the consent form or roster: {exc}",
            }
        return {
            "consent_decisions": review.decisions,
            "consent_form_found": review.consent_form_found,
            "consent_error": None,
        }

    def _update(self, **changes: object) -> None:
        new_state = replace(self._state, **changes)
        if new_state == self._state:
            return
        self._state = new_state
        self.state_changed.emit(self._state)
