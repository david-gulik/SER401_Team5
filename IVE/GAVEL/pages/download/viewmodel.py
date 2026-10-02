from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QApplication

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasCourse, CanvasQuiz
from GAVEL.app.dtos.roster import ClassSection, TermInfo
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.ports.roster_client import RosterClient
from GAVEL.app.usecases.download_all_quizzes import (
    DownloadAllQuizzesRequest,
    DownloadAllQuizzesUseCase,
)
from GAVEL.app.usecases.download_all_rubric_assessments import (
    DownloadAllRubricAssessmentsRequest,
    DownloadAllRubricAssessmentsUseCase,
)
from GAVEL.app.usecases.download_consent_form import (
    DownloadConsentFormRequest,
    DownloadConsentFormUseCase,
)
from GAVEL.app.usecases.download_gradebook import DownloadGradebookRequest, DownloadGradebookUseCase
from GAVEL.app.usecases.download_gradescope_submissions import (
    DownloadGradescopeSubmissionsRequest,
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
from GAVEL.app.workspace.layout import CourseFolder, Workspace
from GAVEL.app.workspace.recording import ArtifactExistsError
from GAVEL.app.workspace.resolve import NOTHING_TO_NAME_FROM, course_key_from_selections
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
RUBRIC_DOWNLOAD = "Rubric Assessment"

# Everything keyed to the selected Canvas course, so a course change resets it.
CANVAS_DOWNLOADS = frozenset(
    {GRADEBOOK_DOWNLOAD, GRADESCOPE_DOWNLOAD, CONSENT_DOWNLOAD, RUBRIC_DOWNLOAD}
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
    def can_download_all_rubric_assessments(self) -> bool:
        return bool(self.selected_course_id)

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


class _WorkerSignals(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(object)


class _BackgroundTask(QRunnable):
    """Runs a callable on QThreadPool, marshalling result/error back via signals."""

    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self._fn = fn
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            value = self._fn()
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(exc)
        else:
            self.signals.result.emit(value)


class DownloadViewModel(QObject):
    state_changed = pyqtSignal(object)  # DownloadUiState
    event_raised = pyqtSignal(object)  # ShowError | ShowInfo

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

    def get_state(self) -> DownloadUiState:
        return self._state

    # Field setters

    def set_term(self, value: str) -> None:
        if value == self._state.selected_term:
            return
        self._state = replace(
            self._state,
            selected_term=value,
            completed=self._state.completed - {ROSTER_DOWNLOAD},
        )
        self.state_changed.emit(self._state)

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
        task = _BackgroundTask(fn)
        task.signals.result.connect(on_result)
        task.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(task)

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
        self._state = replace(
            self._state,
            terms=terms_seq,
            selected_term=default_term,
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
        if not sections_seq:
            self._set_idle(Status.WARNING, "No sections found.")
            return
        sorted_sections = sorted(sections_seq, key=lambda s: (s.subject, s.catalog_number))
        self._state = replace(
            self._state,
            sections=sorted_sections,
            is_busy=False,
            status=Status.NOMINAL,
            message=f"Found {len(sorted_sections)} section(s).",
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
        folder = self._resolved_course_folder()
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
        if self._state.is_busy or not course_id:
            return
        try:
            cid = int(course_id)
        except ValueError:
            return
        self._set_busy("Loading quizzes...")
        try:
            quizzes = self._canvas_client.list_quizzes(cid)
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Failed to load quizzes: {exc}")
            self._set_idle(Status.CRITICAL, str(exc))
            return
        quizzes = sorted(quizzes, key=lambda q: q.name.lower())
        self._state = replace(
            self._state,
            quizzes=quizzes,
            is_busy=False,
            status=Status.NOMINAL,
            message=f"Loaded {len(quizzes)} quiz(zes).",
        )
        self.state_changed.emit(self._state)

    def load_assignments(self, course_id: str) -> None:
        if self._state.is_busy or not course_id:
            return
        try:
            cid = int(course_id)
        except ValueError:
            return
        self._set_busy("Loading assignments...")
        try:
            assignments = self._canvas_client.list_assignments(cid)
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Failed to load assignments: {exc}")
            self._set_idle(Status.CRITICAL, str(exc))
            return
        assignments = sorted(assignments, key=lambda a: a.name.lower())
        self._state = replace(
            self._state,
            assignments=assignments,
            is_busy=False,
            status=Status.NOMINAL,
            message=f"Loaded {len(assignments)} assignment(s).",
        )
        self.state_changed.emit(self._state)

    def load_courses(self) -> None:
        if self._state.is_busy:
            return
        self._set_busy("Loading courses...")
        try:
            courses = self._canvas_client.list_courses()
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Failed to load courses: {exc}")
            self._set_idle(Status.CRITICAL, str(exc))
            return
        courses = sorted(courses, key=course_sort_key)
        self._state = replace(
            self._state,
            courses=courses,
            is_busy=False,
            status=Status.NOMINAL,
            message=f"Loaded {len(courses)} course(s).",
        )
        self.state_changed.emit(self._state)

    def download_gradebook(self) -> None:
        if self._state.is_busy:
            return
        course_id = self._resolved_course_id()
        if course_id is None:
            return
        folder = self._resolved_course_folder()
        if folder is None:
            return

        self._set_busy(f"Downloading gradebook for course {course_id}...")
        try:
            result = DownloadGradebookUseCase(self._canvas_client).execute(
                DownloadGradebookRequest(course_id=course_id, folder=folder)
            )
        except Exception as exc:  # noqa: BLE001
            self._report_download_failure("Gradebook download failed", exc)
            return

        self._state = replace(
            self._state,
            is_busy=False,
            status=Status.NOMINAL,
            message=result.message,
            last_saved_path=str(result.saved_path),
            completed=self._state.completed | {GRADEBOOK_DOWNLOAD},
        )
        self.state_changed.emit(self._state)
        self.event_raised.emit(ShowInfo(result.message))

    def download_gradescope_submissions(self) -> None:
        if self._state.is_busy:
            return
        course_id = self._resolved_course_id()
        if course_id is None:
            return
        folder = self._resolved_course_folder()
        if folder is None:
            return

        self._set_busy(f"Downloading Gradescope submissions for course {course_id}...")
        try:
            result = DownloadGradescopeSubmissionsUseCase(
                self._canvas_client, browser=self._asu_browser
            ).execute(DownloadGradescopeSubmissionsRequest(course_id=course_id, folder=folder))
        except Exception as exc:  # noqa: BLE001
            self._report_download_failure("Gradescope submissions download failed", exc)
            return

        self._state = replace(
            self._state,
            is_busy=False,
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

        self._set_busy(f"Downloading consent form for course {course_id}...")
        try:
            result = DownloadConsentFormUseCase(self._canvas_client).execute(
                DownloadConsentFormRequest(course_id=course_id, quiz_id=quiz_id, folder=folder)
            )
        except Exception as exc:  # noqa: BLE001
            self._report_download_failure("Consent form download failed", exc)
            return

        self._state = replace(
            self._state,
            is_busy=False,
            status=Status.NOMINAL,
            message=result.message,
            last_saved_path=str(result.saved_path),
            completed=self._state.completed | {CONSENT_DOWNLOAD},
        )
        self.state_changed.emit(self._state)
        self.event_raised.emit(ShowInfo(result.message))

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
            f"Downloading rubric assessment(s) for course {course_id}, assignment(s) {ids_text}..."
        )
        # Each assignment is attempted on its own so one bad ID does not
        # block the rest, mirroring the Download All batch.
        use_case = DownloadRubricAssessmentUseCase(self._canvas_client)
        # Only assignments loaded from Canvas carry has_rubric and a name for
        # the folder tag; a typed ID that was never loaded is attempted as-is.
        known = {a.id: a for a in self._state.assignments}
        saved: list[DownloadRubricAssessmentResult] = []
        skipped: list[str] = []
        existing: list[str] = []
        failed: list[str] = []
        for assignment_id in assignment_ids:
            assignment = known.get(assignment_id)
            if assignment is not None and not assignment.has_rubric:
                self._logger.warning(
                    f"Skipped rubric download for '{assignment.name}' "
                    f"(course {course_id}): no rubric attached."
                )
                skipped.append(f"'{assignment.name}' has no rubric attached")
                continue
            if assignment is None:
                assignment = CanvasAssignment(id=assignment_id, name="")
            try:
                result = use_case.execute(
                    DownloadRubricAssessmentRequest(
                        course_id=course_id, assignment=assignment, folder=folder
                    )
                )
            except ArtifactExistsError as exc:
                self._logger.warning(f"Rubric assessment {assignment_id} already downloaded: {exc}")
                existing.append(str(exc))
                continue
            except Exception as exc:  # noqa: BLE001
                self._logger.error(
                    f"Rubric assessment download failed for assignment {assignment_id}: {exc}"
                )
                failed.append(f"{assignment_id}: {exc}")
                continue
            saved.append(result)

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
                self._state, is_busy=False, status=Status.WARNING, message=message
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

    def download_all_rubric_assessments(self) -> None:
        if self._state.is_busy:
            return
        course_id = self._resolved_course_id()
        if course_id is None:
            return
        folder = self._resolved_course_folder()
        if folder is None:
            return

        self._set_busy(f"Downloading all rubric assessments for course {course_id}...")
        try:
            result = DownloadAllRubricAssessmentsUseCase(self._canvas_client).execute(
                DownloadAllRubricAssessmentsRequest(course_id=course_id, folder=folder)
            )
        except Exception as exc:  # noqa: BLE001
            self._report_download_failure("Rubric assessment batch download failed", exc)
            return

        succeeded, skipped, failed = result.succeeded, result.skipped, result.failed
        existing = result.already_downloaded
        last_path = succeeded[-1].saved_path if succeeded else None

        for outcome in skipped:
            self._logger.warning(
                f"Skipped rubric download for '{outcome.assignment_name}' "
                f"(course {course_id}): no rubric attached."
            )

        message = (
            f"Rubric assessments for course {course_id}: "
            f"{len(succeeded)} succeeded, {len(skipped)} skipped, "
            f"{len(existing)} already downloaded, {len(failed)} failed."
        )
        if failed:
            message += " Failed: " + "; ".join(f"{o.assignment_name}: {o.error}" for o in failed)

        status = Status.NOMINAL
        if failed:
            status = Status.WARNING if (succeeded or skipped or existing) else Status.CRITICAL
        elif existing:
            status = Status.WARNING

        completed = self._state.completed
        if succeeded or existing:
            completed = completed | {RUBRIC_DOWNLOAD}
        self._state = replace(
            self._state,
            is_busy=False,
            status=status,
            message=message,
            last_saved_path=str(last_path) if last_path else self._state.last_saved_path,
            completed=completed,
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

        self._set_busy(f"Downloading all quiz reports for course {course_id}...")
        try:
            result = DownloadAllQuizzesUseCase(self._canvas_client).execute(
                DownloadAllQuizzesRequest(course_id=course_id, folder=folder)
            )
        except Exception as exc:  # noqa: BLE001
            self._report_download_failure("Quiz report batch download failed", exc)
            return

        succeeded, skipped, failed = result.succeeded, result.skipped, result.failed
        for outcome in skipped:
            self._logger.warning(
                f"Skipped quiz report for '{outcome.quiz_name}' "
                f"(course {course_id}): {outcome.skipped_reason}"
            )

        quizzes_dir = folder.original.quizzes_dir
        message = (
            f"Quiz reports for course {course_id}: {len(succeeded)} saved to {quizzes_dir}, "
            f"{len(skipped)} skipped, {len(failed)} failed."
        )
        if failed:
            message += " Failed: " + "; ".join(f"{o.quiz_name}: {o.error}" for o in failed)

        status = Status.NOMINAL
        if failed:
            status = Status.WARNING if (succeeded or skipped) else Status.CRITICAL
        elif skipped:
            status = Status.WARNING

        self._state = replace(
            self._state,
            is_busy=False,
            status=status,
            message=message,
            last_saved_path=str(quizzes_dir) if succeeded else self._state.last_saved_path,
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

        self._set_busy("Downloading all data...")
        roster_client = self._client
        canvas_client = self._canvas_client
        asu_browser = self._asu_browser

        def work() -> _DownloadAllResult:
            successes: list[str] = []
            skipped: list[str] = []
            failures: list[str] = []
            completed: set[str] = set()
            last_path: Path | None = None

            def step(name: str, action: Callable[[], Path]) -> None:
                nonlocal last_path
                try:
                    last_path = action()
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
                lambda: (
                    DownloadRosterUseCase(roster_client)
                    .execute(
                        DownloadRosterRequest(term=term, class_number=class_number, folder=folder)
                    )
                    .saved_path
                ),
            )
            step(
                GRADEBOOK_DOWNLOAD,
                lambda: (
                    DownloadGradebookUseCase(canvas_client)
                    .execute(DownloadGradebookRequest(course_id=course_id, folder=folder))
                    .saved_path
                ),
            )
            step(
                GRADESCOPE_DOWNLOAD,
                lambda: (
                    DownloadGradescopeSubmissionsUseCase(canvas_client, browser=asu_browser)
                    .execute(
                        DownloadGradescopeSubmissionsRequest(course_id=course_id, folder=folder)
                    )
                    .saved_path
                ),
            )
            step(
                CONSENT_DOWNLOAD,
                lambda: (
                    DownloadConsentFormUseCase(canvas_client)
                    .execute(
                        DownloadConsentFormRequest(
                            course_id=course_id, quiz_id=consent_quiz_id, folder=folder
                        )
                    )
                    .saved_path
                ),
            )

            try:
                rubric_result = DownloadAllRubricAssessmentsUseCase(canvas_client).execute(
                    DownloadAllRubricAssessmentsRequest(course_id=course_id, folder=folder)
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

    def _set_busy(self, message: str) -> None:
        self._state = replace(self._state, is_busy=True, status=Status.WARNING, message=message)
        self.state_changed.emit(self._state)
        # Flush a paint so the busy bar shows before the synchronous fetch
        # blocks the GUI thread. Drop this once blocking calls move off-thread.
        QApplication.processEvents()

    def _set_idle(self, status: Status, message: str) -> None:
        self._state = replace(self._state, is_busy=False, status=status, message=message)
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
        key, why = course_key_from_selections(
            state.selected_course,
            state.class_number,
            state.selected_term,
            state.selected_section,
            state.manual_course_folder,
        )
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
