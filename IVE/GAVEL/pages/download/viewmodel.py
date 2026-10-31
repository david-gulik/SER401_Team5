from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from PyQt6.QtCore import QObject, pyqtSignal

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasCourse, CanvasQuiz
from GAVEL.app.dtos.roster import ClassSection, TermInfo
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.ports.roster_client import RosterClient
from GAVEL.app.progress import DownloadProgress, ProgressCallback
from GAVEL.app.usecases.download_all_quizzes import (
    DownloadAllQuizzesRequest,
    DownloadAllQuizzesResult,
    DownloadAllQuizzesUseCase,
)
from GAVEL.app.usecases.download_all_rubric_assessments import (
    DownloadAllRubricAssessmentsRequest,
    DownloadAllRubricAssessmentsUseCase,
)
from GAVEL.app.usecases.download_consent_form import (
    DownloadConsentFormRequest,
    DownloadConsentFormResult,
    DownloadConsentFormUseCase,
)
from GAVEL.app.usecases.download_gradebook import (
    DownloadGradebookRequest,
    DownloadGradebookResult,
    DownloadGradebookUseCase,
)
from GAVEL.app.usecases.download_gradescope_submissions import (
    DownloadGradescopeSubmissionsRequest,
    DownloadGradescopeSubmissionsResult,
    DownloadGradescopeSubmissionsUseCase,
)
from GAVEL.app.usecases.download_roster import (
    DownloadRosterRequest,
    DownloadRosterResult,
    DownloadRosterUseCase,
)
from GAVEL.app.usecases.download_rubric_assessment import (
    DownloadRubricAssessmentRequest,
    DownloadRubricAssessmentResult,
    DownloadRubricAssessmentUseCase,
)
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.recording import ArtifactExistsError
from GAVEL.app.workspace.resolve import (
    NOTHING_TO_NAME_FROM,
    course_key_from_selections,
    roster_key_from_selections,
)
from GAVEL.core.background import run_in_background
from GAVEL.core.status import Status
from GAVEL.pages.download.section_match import section_mismatch
from GAVEL.pages.download.sorting import course_sort_key
from GAVEL.services.logger import AppLogger


def course_id_error(text: str) -> str | None:
    """Validation message for a Canvas course ID typed by hand, or None when usable.

    Shared by the Download tab's manual course field (inline feedback) and by
    the view model's final check before any download starts.
    """
    return None if text.isdigit() else "Course IDs are numbers only, like 213877."


def class_number_error(text: str) -> str | None:
    """Validation message for a myASU class number typed by hand, or None when usable."""
    return None if text.isdigit() else "Class numbers are numbers only, like 12345."


def quiz_id_error(text: str) -> str | None:
    """Validation message for a Canvas quiz ID typed by hand, or None when usable."""
    return None if text.isdigit() else "Quiz IDs are numbers only, like 1234567."


ASSIGNMENT_ID_SEPARATOR = ","


def assignment_ids_error(text: str) -> str | None:
    """Validation message for one or more comma-separated Canvas assignment IDs.

    Shared by the Download tab's manual assignment field (inline feedback)
    and by the view model's final check before a rubric download starts.
    """
    parts = [p.strip() for p in text.split(ASSIGNMENT_ID_SEPARATOR)]
    if any(not p for p in parts):
        return "Separate assignment IDs with commas, like 7216983, 7216990."
    if not all(p.isdigit() for p in parts):
        return "Assignment IDs are numbers only, like 7216983. Separate several with commas."
    return None


def parse_assignment_ids(text: str) -> list[int]:
    """Comma-separated assignment IDs as ints, first occurrence wins on duplicates.

    Callers validate with ``assignment_ids_error`` first; this only splits.
    """
    seen: dict[int, None] = {}
    for part in text.split(ASSIGNMENT_ID_SEPARATOR):
        part = part.strip()
        if part:
            seen.setdefault(int(part), None)
    return list(seen)


def term_code_error(text: str) -> str | None:
    """Validation message for a myASU term code typed by hand, or None when usable.

    Term codes are 2[YY][T]: a literal 2, the two-digit year, then the
    semester digit (1 Spring, 4 Summer, 7 Fall, 9 Winter). 2267 is Fall 2026.
    """
    if len(text) == 4 and text.isdigit() and text[0] == "2" and text[3] in "1479":
        return None
    return (
        "Term codes look like 2267: a 2, the two-digit year, then 1, 4, 7, or 9 for the semester."
    )


_ROSTER_NOT_CONFIGURED = (
    "Roster not configured. Set ROSTER_AUTH_METHOD in .env to enable myASU downloads."
)

# Download names as they appear in Download All's summary and in ``completed``.
ROSTER_DOWNLOAD = "Roster"
GRADEBOOK_DOWNLOAD = "Gradebook"
GRADESCOPE_DOWNLOAD = "Gradescope Submissions"
CONSENT_DOWNLOAD = "Consent Form"
QUIZ_REPORTS_DOWNLOAD = "Quiz Reports"
RUBRIC_DOWNLOAD = "Rubric Assessment"

# Everything keyed to the selected Canvas course, so a course change resets it.
CANVAS_DOWNLOADS = frozenset(
    {
        GRADEBOOK_DOWNLOAD,
        GRADESCOPE_DOWNLOAD,
        CONSENT_DOWNLOAD,
        QUIZ_REPORTS_DOWNLOAD,
        RUBRIC_DOWNLOAD,
    }
)


@dataclass(frozen=True)
class DownloadUiState:
    terms: Sequence[TermInfo] = ()
    selected_term: str = ""
    subject: str = ""
    catalog_number: str = ""
    class_number: str = ""
    assignment_ids: str = ""
    courses: Sequence[CanvasCourse] = ()
    quizzes: Sequence[CanvasQuiz] = ()
    assignments: Sequence[CanvasAssignment] = ()
    sections: Sequence[ClassSection] = ()
    selected_course_id: str = ""
    selected_consent_quiz_id: str = ""
    is_busy: bool = False
    status: Status = Status.UNKNOWN
    message: str = "Enter search criteria or a class number."
    # How far the running batch download has got; None when there is no count yet.
    progress: DownloadProgress | None = None
    last_saved_path: str | None = None
    output_dir: str = ""
    # A course folder name typed by the user; overrides the name derived from selections.
    manual_course_folder: str = ""
    roster_configured: bool = True
    # Downloads that succeeded for the current selections; see *_DOWNLOAD above.
    completed: frozenset[str] = frozenset()

    @property
    def selected_course(self) -> CanvasCourse | None:
        """The loaded course behind the selected ID, or None for a typed ID."""
        return next((c for c in self.courses if str(c.id) == self.selected_course_id), None)

    @property
    def selected_section(self) -> ClassSection | None:
        """The searched section behind the class number, or None for a typed one."""
        return next((s for s in self.sections if s.class_number == self.class_number), None)

    @property
    def section_warning(self) -> str | None:
        """Non-blocking notice when the roster class is not in the Canvas course."""
        return section_mismatch(self.class_number, self.selected_course, self.selected_section)

    @property
    def course_folder_name(self) -> str | None:
        """``courses/ser222_25sc_12345`` for the current selections, or None."""
        key, _ = course_key_from_selections(
            self.selected_course,
            self.class_number,
            self.selected_term,
            self.selected_section,
            self.manual_course_folder,
        )
        return None if key is None else f"courses/{key.folder_name}"

    @property
    def course_folder_error(self) -> str | None:
        """Why no course folder can be named yet, or None when one can."""
        _, why = course_key_from_selections(
            self.selected_course,
            self.class_number,
            self.selected_term,
            self.selected_section,
            self.manual_course_folder,
        )
        return why

    def roster_key(self) -> tuple[CourseKey | None, str | None]:
        """``(key, None)`` for the roster's own course folder, else ``(None, why)``."""
        return roster_key_from_selections(
            self.selected_course,
            self.class_number,
            self.selected_term,
            self.selected_section,
            self.manual_course_folder,
        )

    @property
    def roster_folder_name(self) -> str | None:
        """``courses/ser401_26f_11111`` for the roster class, or None.

        The same as ``course_folder_name`` unless the roster class is not part
        of the selected Canvas course.
        """
        key, _ = self.roster_key()
        return None if key is None else f"courses/{key.folder_name}"

    @property
    def roster_folder_error(self) -> str | None:
        """Why no folder can be named for the roster class yet, or None when one can."""
        _, why = self.roster_key()
        return why

    @property
    def canvas_downloads_partial(self) -> bool:
        """Some, but not all, Canvas downloads are done for the selected course."""
        done = self.completed & CANVAS_DOWNLOADS
        return bool(done) and done != CANVAS_DOWNLOADS

    @property
    def can_download_roster(self) -> bool:
        return self.roster_configured and bool(self.selected_term) and bool(self.class_number)

    @property
    def can_download_gradebook(self) -> bool:
        return bool(self.selected_course_id)

    @property
    def can_download_submissions(self) -> bool:
        return bool(self.selected_course_id)

    @property
    def can_download_consent(self) -> bool:
        return bool(self.selected_course_id) and bool(self.selected_consent_quiz_id)

    @property
    def can_download_rubric(self) -> bool:
        return bool(self.selected_course_id) and bool(self.assignment_ids.strip())

    @property
    def can_download_all(self) -> bool:
        return (
            self.can_download_roster
            and self.can_download_gradebook
            and self.can_download_consent
            and self.can_download_submissions
        )

    @property
    def canvas_token_available(self) -> bool:
        return os.getenv("CANVAS_TOKEN") is not None

    @property
    def canvas_credentials_available(self) -> bool:
        return bool(os.getenv("CANVAS_USERNAME")) and bool(os.getenv("CANVAS_PASSWORD"))

    @property
    def can_download_all_quizzes(self) -> bool:
        return bool(self.selected_course_id)


@dataclass(frozen=True)
class ShowError:
    message: str


@dataclass(frozen=True)
class ShowInfo:
    message: str


@dataclass(frozen=True)
class FocusCourseFolder:
    """Put the cursor in the course folder override: the selections could not name one."""


@dataclass(frozen=True)
class _DownloadAllResult:
    successes: tuple[str, ...]
    failures: tuple[str, ...]
    last_saved_path: Path | None
    completed: frozenset[str] = frozenset()
    # Steps left alone because their files were already in the course folder.
    skipped: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RubricBatchResult:
    saved: tuple[DownloadRubricAssessmentResult, ...]
    skipped: tuple[str, ...]
    existing: tuple[str, ...]
    failed: tuple[str, ...]


@dataclass(frozen=True)
class _CourseLists:
    """A course's quiz and assignment lists; None when not asked for, the error if it failed."""

    quizzes: Sequence[CanvasQuiz] | Exception | None
    assignments: Sequence[CanvasAssignment] | Exception | None


RUBRIC_PROGRESS_LABEL = "Downloading rubric assessments"
DOWNLOAD_ALL_STEPS = 6


class DownloadViewModel(QObject):
    state_changed = pyqtSignal(object)  # DownloadUiState
    event_raised = pyqtSignal(object)  # ShowError | ShowInfo
    # Use cases report progress on the worker thread; this carries it to the GUI thread.
    _progress_reported = pyqtSignal(object)  # DownloadProgress

    def __init__(
        self,
        roster_client: RosterClient,
        canvas_client: CanvasClient,
        default_output_dir: Path,
        logger: AppLogger,
        roster_configured: bool,
        asu_browser: object | None = None,
    ) -> None:
        super().__init__()
        self._client = roster_client
        self._canvas_client = canvas_client
        # Shared login browser, handed to the Gradescope download so it reuses
        # the login the roster download (or an earlier run) already made.
        self._asu_browser = asu_browser
        self._default_output_dir = default_output_dir
        self._logger = logger
        self._roster_configured = roster_configured

        initial_msg = "Enter search criteria or a class number."
        initial_status = Status.UNKNOWN
        if not roster_configured:
            initial_msg = "Roster not configured"
            initial_status = Status.CRITICAL

        self._state = DownloadUiState(
            status=initial_status,
            message=initial_msg,
            output_dir=str(default_output_dir),
            roster_configured=roster_configured,
        )
        self._progress_reported.connect(self._on_progress)

    def get_state(self) -> DownloadUiState:
        return self._state

    # Field setters

    def set_term(self, value: str) -> None:
        if value == self._state.selected_term:
            return
        self._state = self._with_term(value)
        self.state_changed.emit(self._state)

    def _with_term(self, term: str) -> DownloadUiState:
        """The state for ``term``: no sections and no roster mark.

        The Download tab empties the Step 2 dropdown in turn, which drops a
        class number picked from it. A typed class number is left alone.
        """
        return replace(
            self._state,
            selected_term=term,
            sections=(),
            completed=self._state.completed - {ROSTER_DOWNLOAD},
        )

    def set_subject(self, value: str) -> None:
        text = value.strip().upper()
        if text == self._state.subject:
            return
        self._state = replace(self._state, subject=text)
        self.state_changed.emit(self._state)

    def set_catalog_number(self, value: str) -> None:
        text = value.strip()
        if text == self._state.catalog_number:
            return
        self._state = replace(self._state, catalog_number=text)
        self.state_changed.emit(self._state)

    def set_class_number(self, value: str) -> None:
        text = value.strip()
        if text == self._state.class_number:
            return
        self._state = replace(
            self._state,
            class_number=text,
            completed=self._state.completed - {ROSTER_DOWNLOAD},
        )
        self.state_changed.emit(self._state)

    def set_course_id(self, value: str) -> None:
        text = value.strip()
        if text == self._state.selected_course_id:
            return
        self._state = replace(
            self._state,
            selected_course_id=text,
            quizzes=(),
            selected_consent_quiz_id="",
            assignments=(),
            assignment_ids="",
            completed=self._state.completed - CANVAS_DOWNLOADS,
        )
        self.state_changed.emit(self._state)
        self._logger.info(f"Selected course ID set to {text}")

    def set_consent_quiz_id(self, value: str) -> None:
        text = value.strip()
        if text == self._state.selected_consent_quiz_id:
            return
        self._state = replace(self._state, selected_consent_quiz_id=text)
        self.state_changed.emit(self._state)
        self._logger.info(f"Selected consent quiz ID set to {text}")

    def set_assignment_ids(self, value: str) -> None:
        """Store the comma-separated assignment IDs the rubric download reads."""
        text = value.strip()
        if text == self._state.assignment_ids:
            return
        self._state = replace(self._state, assignment_ids=text)
        self.state_changed.emit(self._state)
        self._logger.info(f"Selected assignment IDs set to {text}")

    def set_manual_course_folder(self, value: str) -> None:
        """Override the course folder name; empty goes back to naming it from the selections.

        Downloads made so far went into a different folder, so completion marks reset.
        """
        text = value.strip()
        if text == self._state.manual_course_folder:
            return
        self._state = replace(self._state, manual_course_folder=text, completed=frozenset())
        self.state_changed.emit(self._state)

    def set_output_dir(self, value: str) -> None:
        text = value.strip()
        if text == self._state.output_dir:
            return
        self._state = replace(self._state, output_dir=text)
        self.state_changed.emit(self._state)

    def reset_output_dir(self) -> None:
        env_dir = (os.getenv("DEFAULT_OUTPUT_DIR") or "").strip()
        default = env_dir or str(self._default_output_dir)
        if default == self._state.output_dir:
            return
        self._state = replace(self._state, output_dir=default)
        self.state_changed.emit(self._state)

    def _resolve_output_dir(self) -> Path:
        text = self._state.output_dir.strip()
        return Path(text).expanduser() if text else self._default_output_dir

    def _run_async(
        self,
        fn: Callable[[], object],
        on_result: Callable[[object], None],
        on_error: Callable[[object], None],
    ) -> None:
        """Run `fn` on QThreadPool; result/error fire on the GUI thread."""
        run_in_background(fn, on_result, on_error)

    def _report_progress(self, progress: DownloadProgress) -> None:
        """Progress callback handed to use cases; safe to call from the worker thread."""
        self._progress_reported.emit(progress)

    def _on_progress(self, progress: object) -> None:
        if not self._state.is_busy:
            return
        p: DownloadProgress = progress  # type: ignore[assignment]
        message = p.text if p.item is None else f"{p.text}. Last finished: {p.item}"
        self._state = replace(self._state, progress=p, message=message)
        self.state_changed.emit(self._state)

    # Actions

    def load_terms(self) -> None:
        if self._state.is_busy:
            return
        if not self._roster_configured:
            self._emit_error(_ROSTER_NOT_CONFIGURED)
            return
        self._set_busy("Loading terms...")
        self._run_async(
            self._client.list_terms,
            self._on_terms_loaded,
            self._on_load_terms_error,
        )

    def _on_terms_loaded(self, terms: object) -> None:
        terms_seq: Sequence[TermInfo] = terms  # type: ignore[assignment]
        default_term = ""
        for t in terms_seq:
            if t.default:
                default_term = t.code
                break
        if default_term != self._state.selected_term:
            self._state = self._with_term(default_term)
        self._state = replace(
            self._state,
            terms=terms_seq,
            is_busy=False,
            status=Status.NOMINAL,
            message=f"Loaded {len(terms_seq)} terms.",
        )
        self.state_changed.emit(self._state)

    def _on_load_terms_error(self, exc: object) -> None:
        self._logger.error(f"Failed to load terms: {exc}")
        self._set_idle(Status.CRITICAL, str(exc))

    def find_sections(self) -> None:
        if self._state.is_busy:
            return
        if not self._roster_configured:
            self._emit_error(_ROSTER_NOT_CONFIGURED)
            return
        term = self._resolved_term()
        if term is None:
            return
        if not self._state.subject or not self._state.catalog_number:
            self._emit_error("Subject and catalog number are required.")
            return

        self._set_busy("Searching sections...")
        subject = self._state.subject
        catalog = self._state.catalog_number
        self._run_async(
            lambda: self._client.find_sections(term, subject, catalog),
            self._on_sections_found,
            self._on_find_sections_error,
        )

    def _on_sections_found(self, sections: object) -> None:
        sections_seq: Sequence[ClassSection] = sections  # type: ignore[assignment]
        # Every search replaces the list; an empty result leaves it empty.
        sorted_sections = tuple(sorted(sections_seq, key=lambda s: (s.subject, s.catalog_number)))
        if sorted_sections:
            status, message = Status.NOMINAL, f"Found {len(sorted_sections)} section(s)."
        else:
            status, message = Status.WARNING, "No sections found."
        self._state = replace(
            self._state,
            sections=sorted_sections,
            is_busy=False,
            status=status,
            message=message,
        )
        self.state_changed.emit(self._state)

    def _on_find_sections_error(self, exc: object) -> None:
        self._logger.error(f"Section lookup failed: {exc}")
        self._set_idle(Status.CRITICAL, str(exc))
        self.event_raised.emit(ShowError(str(exc)))

    def download_roster(self) -> None:
        if self._state.is_busy:
            return
        if not self._roster_configured:
            self._emit_error(_ROSTER_NOT_CONFIGURED)
            return
        term = self._resolved_term()
        if term is None:
            return
        class_number = self._resolved_class_number()
        if class_number is None:
            return
        folder = self._resolved_roster_folder()
        if folder is None:
            return

        self._set_busy("Authenticating and downloading roster...")
        use_case = DownloadRosterUseCase(self._client)
        request = DownloadRosterRequest(term=term, class_number=class_number, folder=folder)
        self._run_async(
            lambda: use_case.execute(request),
            self._on_roster_downloaded,
            self._on_roster_error,
        )

    def _on_roster_downloaded(self, result: object) -> None:
        res: DownloadRosterResult = result  # type: ignore[assignment]
        self._state = replace(
            self._state,
            is_busy=False,
            status=Status.NOMINAL,
            message=res.message,
            last_saved_path=str(res.saved_path),
            completed=self._state.completed | {ROSTER_DOWNLOAD},
        )
        self.state_changed.emit(self._state)
        self.event_raised.emit(ShowInfo(res.message))

    def _on_roster_error(self, exc: object) -> None:
        self._report_download_failure("Roster download failed", exc)

    def load_quizzes(self, course_id: str) -> None:
        self._load_course_lists(course_id, quizzes=True, assignments=False)

    def load_assignments(self, course_id: str) -> None:
        self._load_course_lists(course_id, quizzes=False, assignments=True)

    def load_course_lists(self, course_id: str) -> None:
        """Quizzes and assignments for a newly picked course, in one background job.

        One job rather than two calls: a second call would find the first
        still running and be turned away by the busy check.
        """
        self._load_course_lists(course_id, quizzes=True, assignments=True)

    def _load_course_lists(self, course_id: str, quizzes: bool, assignments: bool) -> None:
        if self._state.is_busy or not course_id:
            return
        try:
            cid = int(course_id)
        except ValueError:
            return
        wanted = [name for name, on in (("quizzes", quizzes), ("assignments", assignments)) if on]
        self._set_busy(f"Loading {' and '.join(wanted)}...")
        client = self._canvas_client

        def fetch(load: Callable[[int], Sequence]) -> Sequence | Exception:
            # Each list stands alone: a failed quiz list still lets assignments load.
            try:
                return load(cid)
            except Exception as exc:  # noqa: BLE001
                return exc

        def work() -> _CourseLists:
            return _CourseLists(
                quizzes=fetch(client.list_quizzes) if quizzes else None,
                assignments=fetch(client.list_assignments) if assignments else None,
            )

        self._run_async(work, self._on_course_lists_loaded, self._on_list_load_error)

    def _on_course_lists_loaded(self, value: object) -> None:
        lists: _CourseLists = value  # type: ignore[assignment]
        changes: dict[str, object] = {}
        loaded: list[str] = []
        errors: list[str] = []
        if isinstance(lists.quizzes, Exception):
            self._logger.error(f"Failed to load quizzes: {lists.quizzes}")
            errors.append(str(lists.quizzes))
        elif lists.quizzes is not None:
            changes["quizzes"] = sorted(lists.quizzes, key=lambda q: q.name.lower())
            loaded.append(f"Loaded {len(lists.quizzes)} quiz(zes).")
        if isinstance(lists.assignments, Exception):
            self._logger.error(f"Failed to load assignments: {lists.assignments}")
            errors.append(str(lists.assignments))
        elif lists.assignments is not None:
            changes["assignments"] = sorted(lists.assignments, key=lambda a: a.name.lower())
            loaded.append(f"Loaded {len(lists.assignments)} assignment(s).")

        self._state = replace(
            self._state,
            **changes,
            is_busy=False,
            progress=None,
            status=Status.CRITICAL if errors else Status.NOMINAL,
            message="; ".join(errors) if errors else " ".join(loaded),
        )
        self.state_changed.emit(self._state)

    def load_courses(self) -> None:
        if self._state.is_busy:
            return
        self._set_busy("Loading courses...")
        self._run_async(
            self._canvas_client.list_courses,
            self._on_courses_loaded,
            self._on_list_load_error,
        )

    def _on_courses_loaded(self, value: object) -> None:
        courses = sorted(value, key=course_sort_key)  # type: ignore[call-overload]
        self._state = replace(
            self._state,
            courses=courses,
            is_busy=False,
            status=Status.NOMINAL,
            message=f"Loaded {len(courses)} course(s).",
        )
        self.state_changed.emit(self._state)

    def _on_list_load_error(self, exc: object) -> None:
        self._logger.error(f"Failed to load from Canvas: {exc}")
        self._set_idle(Status.CRITICAL, str(exc))

    def download_gradebook(self) -> None:
        if self._state.is_busy:
            return
        course_id = self._resolved_course_id()
        if course_id is None:
            return
        folder = self._resolved_course_folder()
        if folder is None:
            return

        label = f"Downloading gradebook for course {course_id}"
        self._set_busy(f"{label}...", DownloadProgress(label, 0, 0))
        use_case = DownloadGradebookUseCase(self._canvas_client)
        request = DownloadGradebookRequest(course_id=course_id, folder=folder)
        self._run_async(
            lambda: use_case.execute(request),
            lambda result: self._on_single_download(GRADEBOOK_DOWNLOAD, result),
            lambda exc: self._report_download_failure("Gradebook download failed", exc),
        )

    def _on_single_download(self, name: str, result: object) -> None:
        """Finish a one-file download: the gradebook or the consent form."""
        res: DownloadGradebookResult | DownloadConsentFormResult = result  # type: ignore[assignment]
        self._state = replace(
            self._state,
            is_busy=False,
            progress=None,
            status=Status.NOMINAL,
            message=res.message,
            last_saved_path=str(res.saved_path),
            completed=self._state.completed | {name},
        )
        self.state_changed.emit(self._state)
        self.event_raised.emit(ShowInfo(res.message))

    def download_gradescope_submissions(self) -> None:
        if self._state.is_busy:
            return
        course_id = self._resolved_course_id()
        if course_id is None:
            return
        folder = self._resolved_course_folder()
        if folder is None:
            return

        label = f"Signing in to Gradescope for course {course_id}"
        self._set_busy(f"{label}...", DownloadProgress(label, 0, 0))
        use_case = DownloadGradescopeSubmissionsUseCase(
            self._canvas_client, browser=self._asu_browser
        )
        request = DownloadGradescopeSubmissionsRequest(course_id=course_id, folder=folder)
        self._run_async(
            lambda: use_case.execute(request, on_progress=self._report_progress),
            self._on_gradescope_downloaded,
            lambda exc: self._report_download_failure(
                "Gradescope submissions download failed", exc
            ),
        )

    def _on_gradescope_downloaded(self, value: object) -> None:
        result: DownloadGradescopeSubmissionsResult = value  # type: ignore[assignment]
        self._state = replace(
            self._state,
            is_busy=False,
            progress=None,
            status=Status.WARNING if result.unmatched else Status.NOMINAL,
            message=result.message,
            last_saved_path=str(result.saved_path),
            completed=self._state.completed | {GRADESCOPE_DOWNLOAD},
        )
        self.state_changed.emit(self._state)
        self.event_raised.emit(ShowInfo(result.message))

    def download_consent(self) -> None:
        if self._state.is_busy:
            return
        course_id = self._resolved_course_id()
        if course_id is None:
            return
        quiz_id = self._resolved_quiz_id()
        if quiz_id is None:
            return
        folder = self._resolved_course_folder()
        if folder is None:
            return

        label = f"Downloading consent form for course {course_id}"
        self._set_busy(f"{label}...", DownloadProgress(label, 0, 0))
        use_case = DownloadConsentFormUseCase(self._canvas_client)
        request = DownloadConsentFormRequest(course_id=course_id, quiz_id=quiz_id, folder=folder)
        self._run_async(
            lambda: use_case.execute(request),
            lambda result: self._on_single_download(CONSENT_DOWNLOAD, result),
            lambda exc: self._report_download_failure("Consent form download failed", exc),
        )

    def download_rubric_assessment(self) -> None:
        if self._state.is_busy:
            return
        course_id = self._resolved_course_id()
        if course_id is None:
            return
        assignment_ids = self._resolved_assignment_ids()
        if assignment_ids is None:
            return
        folder = self._resolved_course_folder()
        if folder is None:
            return

        ids_text = ", ".join(str(a) for a in assignment_ids)
        self._set_busy(
            f"Downloading rubric assessment(s) for course {course_id}, assignment(s) {ids_text}...",
            DownloadProgress(RUBRIC_PROGRESS_LABEL, 0, len(assignment_ids)),
        )
        # Each assignment is attempted on its own so one bad ID does not
        # block the rest, mirroring the Download All batch.
        use_case = DownloadRubricAssessmentUseCase(self._canvas_client)
        # Only assignments loaded from Canvas carry has_rubric and a name for
        # the folder tag; a typed ID that was never loaded is attempted as-is.
        known = {a.id: a for a in self._state.assignments}
        logger = self._logger
        report_progress = self._report_progress
        total = len(assignment_ids)

        def work() -> _RubricBatchResult:
            saved: list[DownloadRubricAssessmentResult] = []
            skipped: list[str] = []
            existing: list[str] = []
            failed: list[str] = []
            for index, assignment_id in enumerate(assignment_ids, start=1):
                assignment = known.get(assignment_id)
                name = assignment.name if assignment is not None else ""
                logger.info(
                    f"Rubric assessment {index} of {total}: "
                    f"'{name or assignment_id}' (course {course_id})"
                )
                if assignment is not None and not assignment.has_rubric:
                    logger.warning(
                        f"Skipped rubric download for '{assignment.name}' "
                        f"(course {course_id}): no rubric attached."
                    )
                    skipped.append(f"'{assignment.name}' has no rubric attached")
                else:
                    if assignment is None:
                        assignment = CanvasAssignment(id=assignment_id, name="")
                    try:
                        result = use_case.execute(
                            DownloadRubricAssessmentRequest(
                                course_id=course_id, assignment=assignment, folder=folder
                            )
                        )
                    except ArtifactExistsError as exc:
                        logger.warning(
                            f"Rubric assessment {assignment_id} already downloaded: {exc}"
                        )
                        existing.append(str(exc))
                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            f"Rubric assessment download failed for assignment "
                            f"{assignment_id}: {exc}"
                        )
                        failed.append(f"{assignment_id}: {exc}")
                    else:
                        logger.info(f"Rubric assessment saved to {result.saved_path}")
                        saved.append(result)
                report_progress(
                    DownloadProgress(
                        RUBRIC_PROGRESS_LABEL, index, total, name or str(assignment_id)
                    )
                )
            return _RubricBatchResult(
                saved=tuple(saved),
                skipped=tuple(skipped),
                existing=tuple(existing),
                failed=tuple(failed),
            )

        self._run_async(
            work,
            lambda value: self._on_rubric_downloaded(course_id, value),
            lambda exc: self._report_download_failure("Rubric assessment download failed", exc),
        )

    def _on_rubric_downloaded(self, course_id: int, value: object) -> None:
        res: _RubricBatchResult = value  # type: ignore[assignment]
        saved, skipped, existing, failed = res.saved, res.skipped, res.existing, res.failed

        if not saved and failed:
            message = "; ".join(failed)
            if skipped:
                message += ". Skipped: " + "; ".join(skipped)
            if existing:
                message += ". Already downloaded: " + "; ".join(existing)
            self._set_idle(Status.CRITICAL, message)
            self.event_raised.emit(ShowError(message))
            return

        if not saved:
            # Everything was skipped or already there: nothing fetched, nothing written.
            parts = []
            if skipped:
                parts.append(
                    "Skipped: " + "; ".join(skipped) + ". "
                    "No rubric-level data will be produced for these assignments."
                )
            if existing:
                parts.append("Already downloaded: " + "; ".join(existing))
            message = " ".join(parts)
            self._state = replace(
                self._state, is_busy=False, progress=None, status=Status.WARNING, message=message
            )
            self.state_changed.emit(self._state)
            self.event_raised.emit(ShowInfo(message))
            return

        if len(saved) == 1 and not failed and not skipped and not existing:
            message = saved[0].message
        else:
            counts = [f"{len(saved)} saved"]
            if skipped:
                counts.append(f"{len(skipped)} skipped")
            if existing:
                counts.append(f"{len(existing)} already downloaded")
            counts.append(f"{len(failed)} failed")
            message = f"Rubric assessments for course {course_id}: " + ", ".join(counts) + "."
            if skipped:
                message += " Skipped: " + "; ".join(skipped) + "."
            if existing:
                message += " Already downloaded: " + "; ".join(existing)
            if failed:
                message += " Failed: " + "; ".join(failed)

        self._state = replace(
            self._state,
            is_busy=False,
            progress=None,
            status=Status.WARNING if (failed or skipped or existing) else Status.NOMINAL,
            message=message,
            last_saved_path=str(saved[-1].saved_path),
            completed=self._state.completed | {RUBRIC_DOWNLOAD},
        )
        self.state_changed.emit(self._state)
        if failed:
            self.event_raised.emit(ShowError(message))
        else:
            self.event_raised.emit(ShowInfo(message))

    def download_all_quizzes(self) -> None:
        if self._state.is_busy:
            return
        course_id = self._resolved_course_id()
        if course_id is None:
            return
        folder = self._resolved_course_folder()
        if folder is None:
            return

        label = f"Listing quizzes for course {course_id}"
        self._set_busy(f"{label}...", DownloadProgress(label, 0, 0))
        use_case = DownloadAllQuizzesUseCase(self._canvas_client)
        request = DownloadAllQuizzesRequest(course_id=course_id, folder=folder)
        self._run_async(
            lambda: use_case.execute(request, on_progress=self._report_progress),
            lambda value: self._on_quizzes_downloaded(course_id, folder, value),
            lambda exc: self._report_download_failure("Quiz report batch download failed", exc),
        )

    def _on_quizzes_downloaded(self, course_id: int, folder: CourseFolder, value: object) -> None:
        result: DownloadAllQuizzesResult = value  # type: ignore[assignment]
        succeeded, skipped, failed = result.succeeded, result.skipped, result.failed
        existing = result.already_downloaded
        for outcome in skipped:
            self._logger.warning(
                f"Skipped quiz report for '{outcome.quiz_name}' "
                f"(course {course_id}): {outcome.skipped_reason}"
            )

        quizzes_dir = folder.original.quizzes_dir
        message = (
            f"Quiz reports for course {course_id}: {len(succeeded)} saved to {quizzes_dir}, "
            f"{len(existing)} already downloaded, {len(skipped) - len(existing)} skipped, "
            f"{len(failed)} failed."
        )
        if failed:
            message += " Failed: " + "; ".join(f"{o.quiz_name}: {o.error}" for o in failed)

        status = Status.NOMINAL
        if failed:
            status = Status.WARNING if (succeeded or skipped) else Status.CRITICAL
        elif skipped:
            status = Status.WARNING

        # Reports already in the folder count too: a rerun finds them all there.
        completed = self._state.completed
        if succeeded or existing:
            completed = completed | {QUIZ_REPORTS_DOWNLOAD}
        self._state = replace(
            self._state,
            is_busy=False,
            progress=None,
            status=status,
            message=message,
            last_saved_path=str(quizzes_dir) if succeeded else self._state.last_saved_path,
            completed=completed,
        )
        self.state_changed.emit(self._state)
        if failed:
            self.event_raised.emit(ShowError(message))
        else:
            self.event_raised.emit(ShowInfo(message))

    def download_all(self) -> None:
        if self._state.is_busy:
            return
        if not self._roster_configured:
            self._emit_error(_ROSTER_NOT_CONFIGURED)
            return
        term = self._resolved_term()
        if term is None:
            return
        class_number = self._resolved_class_number()
        if class_number is None:
            return

        course_id = self._resolved_course_id()
        if course_id is None:
            return
        consent_quiz_id = self._resolved_quiz_id()
        if consent_quiz_id is None:
            return
        folder = self._resolved_course_folder()
        if folder is None:
            return
        roster_folder = self._resolved_roster_folder()
        if roster_folder is None:
            return

        self._set_busy("Downloading all data...", DownloadProgress("Starting Download All", 0, 0))
        roster_client = self._client
        canvas_client = self._canvas_client
        asu_browser = self._asu_browser
        report_progress = self._report_progress
        logger = self._logger

        def work() -> _DownloadAllResult:
            successes: list[str] = []
            skipped: list[str] = []
            failures: list[str] = []
            completed: set[str] = set()
            last_path: Path | None = None
            step_number = 0

            def begin(name: str) -> ProgressCallback:
                """Announce the next step; returns a callback that tags its item counts."""
                nonlocal step_number
                step_number += 1
                stage = f"Step {step_number} of {DOWNLOAD_ALL_STEPS}"
                logger.info(f"Download All {stage}: {name}")
                report_progress(DownloadProgress(f"{stage}: {name}", 0, 0))
                return lambda p: report_progress(replace(p, label=f"{stage}: {p.label}"))

            def step(name: str, action: Callable[[ProgressCallback], Path]) -> None:
                nonlocal last_path
                on_progress = begin(name)
                try:
                    last_path = action(on_progress)
                except ArtifactExistsError as exc:
                    skipped.append(f"{name}: {exc}")
                    completed.add(name)
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"{name}: {exc}")
                else:
                    successes.append(name)
                    completed.add(name)

            step(
                ROSTER_DOWNLOAD,
                lambda _: (
                    DownloadRosterUseCase(roster_client)
                    .execute(
                        DownloadRosterRequest(
                            term=term, class_number=class_number, folder=roster_folder
                        )
                    )
                    .saved_path
                ),
            )
            step(
                GRADEBOOK_DOWNLOAD,
                lambda _: (
                    DownloadGradebookUseCase(canvas_client)
                    .execute(DownloadGradebookRequest(course_id=course_id, folder=folder))
                    .saved_path
                ),
            )
            step(
                GRADESCOPE_DOWNLOAD,
                lambda on_progress: (
                    DownloadGradescopeSubmissionsUseCase(canvas_client, browser=asu_browser)
                    .execute(
                        DownloadGradescopeSubmissionsRequest(course_id=course_id, folder=folder),
                        on_progress=on_progress,
                    )
                    .saved_path
                ),
            )
            step(
                CONSENT_DOWNLOAD,
                lambda _: (
                    DownloadConsentFormUseCase(canvas_client)
                    .execute(
                        DownloadConsentFormRequest(
                            course_id=course_id, quiz_id=consent_quiz_id, folder=folder
                        )
                    )
                    .saved_path
                ),
            )

            on_progress = begin(QUIZ_REPORTS_DOWNLOAD)
            try:
                quiz_result = DownloadAllQuizzesUseCase(canvas_client).execute(
                    DownloadAllQuizzesRequest(course_id=course_id, folder=folder),
                    on_progress=on_progress,
                )
                for outcome in quiz_result.succeeded:
                    successes.append(f"{QUIZ_REPORTS_DOWNLOAD} ({outcome.quiz_name})")
                    completed.add(QUIZ_REPORTS_DOWNLOAD)
                    last_path = outcome.saved_path
                for outcome in quiz_result.skipped:
                    if outcome.already_downloaded:
                        skipped.append(f"{QUIZ_REPORTS_DOWNLOAD} ({outcome.quiz_name})")
                        completed.add(QUIZ_REPORTS_DOWNLOAD)
                    else:
                        successes.append(
                            f"{QUIZ_REPORTS_DOWNLOAD} ({outcome.quiz_name}) [skipped: no report]"
                        )
                for outcome in quiz_result.failed:
                    failures.append(
                        f"{QUIZ_REPORTS_DOWNLOAD} ({outcome.quiz_name}): {outcome.error}"
                    )
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{QUIZ_REPORTS_DOWNLOAD}: {exc}")

            on_progress = begin(RUBRIC_DOWNLOAD)
            try:
                rubric_result = DownloadAllRubricAssessmentsUseCase(canvas_client).execute(
                    DownloadAllRubricAssessmentsRequest(course_id=course_id, folder=folder),
                    on_progress=on_progress,
                )
                for outcome in rubric_result.succeeded:
                    successes.append(f"{RUBRIC_DOWNLOAD} ({outcome.assignment_name})")
                    completed.add(RUBRIC_DOWNLOAD)
                    last_path = outcome.saved_path
                for outcome in rubric_result.skipped:
                    successes.append(
                        f"{RUBRIC_DOWNLOAD} ({outcome.assignment_name}) [skipped: no rubric]"
                    )
                for outcome in rubric_result.already_downloaded:
                    skipped.append(f"{RUBRIC_DOWNLOAD} ({outcome.assignment_name})")
                    completed.add(RUBRIC_DOWNLOAD)
                for outcome in rubric_result.failed:
                    failures.append(
                        f"{RUBRIC_DOWNLOAD} ({outcome.assignment_name}): {outcome.error}"
                    )
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{RUBRIC_DOWNLOAD}: {exc}")

            return _DownloadAllResult(
                successes=tuple(successes),
                failures=tuple(failures),
                last_saved_path=last_path,
                completed=frozenset(completed),
                skipped=tuple(skipped),
            )

        self._run_async(work, self._on_download_all_complete, self._on_download_all_error)

    def _on_download_all_complete(self, result: object) -> None:
        res: _DownloadAllResult = result  # type: ignore[assignment]

        if res.failures and not res.successes:
            status = Status.CRITICAL
            message = f"All downloads failed: {'; '.join(res.failures)}"
        elif res.failures:
            status = Status.WARNING
            message = (
                f"Completed with errors. Succeeded: {', '.join(res.successes)}. "
                f"Failed: {'; '.join(res.failures)}"
            )
        elif res.skipped and not res.successes:
            status = Status.WARNING
            message = f"Nothing new to download. Already downloaded: {'; '.join(res.skipped)}"
        elif res.skipped:
            status = Status.WARNING
            message = f"Downloads complete: {', '.join(res.successes)}."
        else:
            status = Status.NOMINAL
            message = f"All downloads complete: {', '.join(res.successes)}."
        if res.skipped and res.successes:
            message += f" Already downloaded: {'; '.join(res.skipped)}"

        last_saved = (
            str(res.last_saved_path) if res.last_saved_path else self._state.last_saved_path
        )
        self._state = replace(
            self._state,
            is_busy=False,
            progress=None,
            status=status,
            message=message,
            last_saved_path=last_saved,
            completed=self._state.completed | res.completed,
        )
        self.state_changed.emit(self._state)

        if res.failures:
            self.event_raised.emit(ShowError(message))
        else:
            self.event_raised.emit(ShowInfo(message))

    def _on_download_all_error(self, exc: object) -> None:
        self._logger.error(f"Download all failed: {exc}")
        self._set_idle(Status.CRITICAL, str(exc))
        self.event_raised.emit(ShowError(str(exc)))

    def recheck(self) -> None:
        load_dotenv(find_dotenv(usecwd=True), override=True)
        self.state_changed.emit(self._state)

    # Helpers

    def _set_busy(self, message: str, progress: DownloadProgress | None = None) -> None:
        """``progress`` marks a batch download, which the tab shows in its progress panel."""
        self._state = replace(
            self._state, is_busy=True, progress=progress, status=Status.WARNING, message=message
        )
        self.state_changed.emit(self._state)

    def _set_idle(self, status: Status, message: str) -> None:
        self._state = replace(
            self._state, is_busy=False, progress=None, status=status, message=message
        )
        self.state_changed.emit(self._state)

    def _emit_error(self, message: str) -> None:
        self._set_idle(Status.CRITICAL, message)
        self.event_raised.emit(ShowError(message))

    def _resolved_course_folder(self) -> CourseFolder | None:
        """The one course folder every download writes into, or None after an error.

        Named from the selections (Canvas course code first, then the roster
        term and section); the Download tab previews the same answer live via
        ``DownloadUiState.course_folder_name``.
        """
        state = self._state
        return self._course_folder_for(
            *course_key_from_selections(
                state.selected_course,
                state.class_number,
                state.selected_term,
                state.selected_section,
                state.manual_course_folder,
            )
        )

    def _resolved_roster_folder(self) -> CourseFolder | None:
        """The course folder the roster download writes into, or None after an error.

        Named for the roster class, never for a Canvas course it is not part
        of; see ``roster_key_from_selections``.
        """
        return self._course_folder_for(*self._state.roster_key())

    def _course_folder_for(self, key: CourseKey | None, why: str | None) -> CourseFolder | None:
        if key is None:
            self._emit_error(why or NOTHING_TO_NAME_FROM)
            self.event_raised.emit(FocusCourseFolder())
            return None
        return Workspace(self._resolve_output_dir()).course(key)

    def _report_download_failure(self, prefix: str, exc: object) -> None:
        """Already-downloaded is a warning the user asked for; anything else is an error."""
        if isinstance(exc, ArtifactExistsError):
            self._logger.warning(f"{prefix}: {exc}")
            self._set_idle(Status.WARNING, str(exc))
            self.event_raised.emit(ShowInfo(str(exc)))
            return
        self._logger.error(f"{prefix}: {exc}")
        self._set_idle(Status.CRITICAL, str(exc))
        self.event_raised.emit(ShowError(str(exc)))

    def _resolved_course_id(self) -> int | None:
        """The one course id every Canvas download reads.

        The Download tab feeds ``set_course_id`` from a single InputModeToggle,
        so the stored value is normally already validated. This is the last
        line of defence: it reports a clear error and returns None rather than
        letting a download start with nothing usable.
        """
        text = self._state.selected_course_id.strip()
        if not text:
            self._emit_error("Select a course first.")
            return None
        error = course_id_error(text)
        if error:
            self._emit_error(f"Invalid course ID {text!r}. {error}")
            return None
        return int(text)

    def _resolved_class_number(self) -> str | None:
        """The one class number the roster download and Download All read.

        Fed by the Download tab's Section InputModeToggle, which already
        resolves "searched section" versus "typed class number" to a single
        value, so there is nothing to fall back to here.
        """
        text = self._state.class_number.strip()
        if not text:
            self._emit_error("Search for a section or enter a class number first.")
            return None
        error = class_number_error(text)
        if error:
            self._emit_error(f"Invalid class number {text!r}. {error}")
            return None
        return text

    def _resolved_quiz_id(self) -> int | None:
        """The one consent quiz id the consent download and Download All read."""
        text = self._state.selected_consent_quiz_id.strip()
        if not text:
            self._emit_error("Select a consent quiz first.")
            return None
        error = quiz_id_error(text)
        if error:
            self._emit_error(f"Invalid consent quiz ID {text!r}. {error}")
            return None
        return int(text)

    def _resolved_assignment_ids(self) -> list[int] | None:
        """The assignment ids the rubric download reads, in the order given.

        Fed by the Download tab's Rubric Assessment InputModeToggle, which
        already joins checked assignments or typed IDs into one string.
        """
        text = self._state.assignment_ids.strip()
        if not text:
            self._emit_error("Select or enter at least one assignment first.")
            return None
        error = assignment_ids_error(text)
        if error:
            self._emit_error(f"Invalid assignment IDs {text!r}. {error}")
            return None
        return parse_assignment_ids(text)

    def _resolved_term(self) -> str | None:
        """The one term code the section search, roster download, and Download All read."""
        text = self._state.selected_term.strip()
        if not text:
            self._emit_error("Select a term first.")
            return None
        error = term_code_error(text)
        if error:
            self._emit_error(f"Invalid term code {text!r}. {error}")
            return None
        return text
