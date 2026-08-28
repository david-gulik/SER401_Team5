from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QApplication

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasCourse, CanvasQuiz
from GAVEL.app.dtos.roster import ClassSection, RosterRequest, TermInfo
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.ports.roster_client import RosterClient
from GAVEL.app.usecases.download_consent_form import (
    DownloadConsentFormRequest,
    DownloadConsentFormUseCase,
)
from GAVEL.app.usecases.download_gradebook import DownloadGradebookRequest, DownloadGradebookUseCase
from GAVEL.app.usecases.download_gradescope_submissions import (
    DownloadGradescopeSubmissionsRequest,
    DownloadGradescopeSubmissionsUseCase,
)
from GAVEL.app.usecases.download_rubric_assessment import (
    DownloadRubricAssessmentRequest,
    DownloadRubricAssessmentUseCase,
)
from GAVEL.app.usecases.roster import download_roster_to_file
from GAVEL.core.status import Status
from GAVEL.services.logger import AppLogger


@dataclass(frozen=True)
class DownloadUiState:
    terms: Sequence[TermInfo] = ()
    selected_term: str = ""
    subject: str = ""
    catalog_number: str = ""
    class_number: str = ""
    assignment_id: str = ""
    courses: Sequence[CanvasCourse] = ()
    quizzes: Sequence[CanvasQuiz] = ()
    assignments: Sequence[CanvasAssignment] = ()
    sections: Sequence[ClassSection] = ()
    selected_section_idx: int = -1
    selected_course_id: str = ""
    selected_consent_quiz_id: str = ""
    is_busy: bool = False
    status: Status = Status.UNKNOWN
    message: str = "Enter search criteria or a class number."
    last_saved_path: str | None = None
    output_dir: str = ""

    @property
    def can_download_roster(self) -> bool:
        has_term = bool(self.selected_term)
        has_section = self.selected_section_idx >= 0 or bool(self.class_number)
        return has_term and has_section

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
        return bool(self.selected_course_id) and bool(self.assignment_id.strip())

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


@dataclass(frozen=True)
class ShowError:
    message: str


@dataclass(frozen=True)
class ShowInfo:
    message: str


def course_sort_key(course: CanvasCourse) -> tuple[str, str, int]:
    """Ordering rule for Canvas course selection entries.

    Sorts on the text the dropdown actually shows - the course code when Canvas
    supplies one, the course name otherwise - then on name and id so the order is
    total and comes out identical on every reload.
    """
    primary = (course.course_code or course.name or "").strip().casefold()
    return (primary, (course.name or "").strip().casefold(), course.id)


@dataclass(frozen=True)
class _DownloadAllResult:
    successes: tuple[str, ...]
    failures: tuple[str, ...]
    last_saved_path: Path | None


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
    ) -> None:
        super().__init__()
        self._client = roster_client
        self._canvas_client = canvas_client
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
        )

    def get_state(self) -> DownloadUiState:
        return self._state

    # Field setters

    def set_term(self, value: str) -> None:
        if value == self._state.selected_term:
            return
        self._state = replace(self._state, selected_term=value)
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
        self._state = replace(self._state, class_number=text)
        self.state_changed.emit(self._state)

    def set_selected_section(self, index: int) -> None:
        if index == self._state.selected_section_idx:
            return
        self._state = replace(self._state, selected_section_idx=index)
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
            assignment_id="",
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

    def set_assignment_id(self, value: str) -> None:
        text = value.strip()
        if text == self._state.assignment_id:
            return
        self._state = replace(self._state, assignment_id=text)
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
        if self._state.is_busy or not self._roster_configured:
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
        if self._state.is_busy or not self._roster_configured:
            return
        if not self._state.selected_term:
            self._emit_error("Select a term first.")
            return
        if not self._state.subject or not self._state.catalog_number:
            self._emit_error("Subject and catalog number are required.")
            return

        self._set_busy("Searching sections...")
        term = self._state.selected_term
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
            selected_section_idx=0,
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
        if self._state.is_busy or not self._roster_configured:
            return

        class_number = self._state.class_number.strip()
        if not class_number and self._state.sections and self._state.selected_section_idx >= 0:
            class_number = self._state.sections[self._state.selected_section_idx].class_number

        if not class_number:
            self._emit_error("Provide a class number directly, or search for sections first.")
            return
        if not self._state.selected_term:
            self._emit_error("Select a term first.")
            return

        self._set_busy("Authenticating and downloading roster...")
        request = RosterRequest(
            term=self._state.selected_term,
            class_number=class_number,
        )
        out_path = self._resolve_output_dir() / f"roster_{request.term}_{class_number}.csv"

        def work() -> Path:
            try:
                self._client.authenticate()
                download_roster_to_file(self._client, request, out_path)
            finally:
                self._client.close()
            return out_path

        self._run_async(
            work,
            self._on_roster_downloaded,
            self._on_roster_error,
        )

    def _on_roster_downloaded(self, out_path: object) -> None:
        msg = f"Roster saved to {out_path}"
        self._state = replace(
            self._state,
            is_busy=False,
            status=Status.NOMINAL,
            message=msg,
            last_saved_path=str(out_path),
        )
        self.state_changed.emit(self._state)
        self.event_raised.emit(ShowInfo(msg))

    def _on_roster_error(self, exc: object) -> None:
        self._logger.error(f"Roster download failed: {exc}")
        self._set_idle(Status.CRITICAL, str(exc))
        self.event_raised.emit(ShowError(str(exc)))

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
        course_id_str = self._state.selected_course_id.strip()
        if not course_id_str:
            self._emit_error("Select a course first.")
            return
        try:
            course_id = int(course_id_str)
        except ValueError:
            self._emit_error(f"Invalid course ID: {course_id_str!r}")
            return

        self._set_busy(f"Downloading gradebook for course {course_id}...")
        try:
            result = DownloadGradebookUseCase(self._canvas_client).execute(
                DownloadGradebookRequest(course_id=course_id, output_dir=self._resolve_output_dir())
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Gradebook download failed: {exc}")
            self._set_idle(Status.CRITICAL, str(exc))
            self.event_raised.emit(ShowError(str(exc)))
            return

        self._state = replace(
            self._state,
            is_busy=False,
            status=Status.NOMINAL,
            message=result.message,
            last_saved_path=str(result.saved_path),
        )
        self.state_changed.emit(self._state)
        self.event_raised.emit(ShowInfo(result.message))

    def download_gradescope_submissions(self) -> None:
        if self._state.is_busy:
            return
        course_id_str = self._state.selected_course_id.strip()
        if not course_id_str:
            self._emit_error("Select a course first.")
            return
        try:
            course_id = int(course_id_str)
        except ValueError:
            self._emit_error(f"Invalid course ID: {course_id_str!r}")
            return

        self._set_busy(f"Downloading Gradescope submissions for course {course_id}...")
        try:
            result = DownloadGradescopeSubmissionsUseCase().execute(
                DownloadGradescopeSubmissionsRequest(
                    course_id=course_id, output_dir=self._resolve_output_dir()
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Gradescope submissions download failed: {exc}")
            self._set_idle(Status.CRITICAL, str(exc))
            self.event_raised.emit(ShowError(str(exc)))
            return

        self._state = replace(
            self._state,
            is_busy=False,
            status=Status.NOMINAL,
            message=result.message,
            last_saved_path=str(result.saved_path),
        )
        self.state_changed.emit(self._state)
        self.event_raised.emit(ShowInfo(result.message))

    def download_consent(self) -> None:
        if self._state.is_busy:
            return
        course_id_str = self._state.selected_course_id.strip()
        quiz_id_str = self._state.selected_consent_quiz_id.strip()
        if not course_id_str:
            self._emit_error("Select a course first.")
            return
        if not quiz_id_str:
            self._emit_error("Select a consent quiz first.")
            return
        try:
            course_id = int(course_id_str)
            quiz_id = int(quiz_id_str)
        except ValueError:
            self._emit_error("Invalid course or quiz ID.")
            return

        self._set_busy(f"Downloading consent form for course {course_id}...")
        try:
            result = DownloadConsentFormUseCase(self._canvas_client).execute(
                DownloadConsentFormRequest(
                    course_id=course_id, quiz_id=quiz_id, output_dir=self._resolve_output_dir()
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Consent form download failed: {exc}")
            self._set_idle(Status.CRITICAL, str(exc))
            self.event_raised.emit(ShowError(str(exc)))
            return

        self._state = replace(
            self._state,
            is_busy=False,
            status=Status.NOMINAL,
            message=result.message,
            last_saved_path=str(result.saved_path),
        )
        self.state_changed.emit(self._state)
        self.event_raised.emit(ShowInfo(result.message))

    def download_rubric_assessment(self) -> None:
        if self._state.is_busy:
            return
        course_id_str = self._state.selected_course_id.strip()
        assignment_id_str = self._state.assignment_id.strip()
        if not course_id_str:
            self._emit_error("Select a course first.")
            return
        if not assignment_id_str:
            self._emit_error("Enter an assignment ID first.")
            return
        try:
            course_id = int(course_id_str)
            assignment_id = int(assignment_id_str)
        except ValueError:
            self._emit_error("Course ID and Assignment ID must be numeric.")
            return

        self._set_busy(
            f"Downloading rubric assessment for course {course_id}, assignment {assignment_id}..."
        )
        try:
            result = DownloadRubricAssessmentUseCase(self._canvas_client).execute(
                DownloadRubricAssessmentRequest(
                    course_id=course_id,
                    assignment_id=assignment_id,
                    output_dir=self._resolve_output_dir(),
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Rubric assessment download failed: {exc}")
            self._set_idle(Status.CRITICAL, str(exc))
            self.event_raised.emit(ShowError(str(exc)))
            return

        self._state = replace(
            self._state,
            is_busy=False,
            status=Status.NOMINAL,
            message=result.message,
            last_saved_path=str(result.saved_path),
        )
        self.state_changed.emit(self._state)
        self.event_raised.emit(ShowInfo(result.message))

    def download_all(self) -> None:
        if self._state.is_busy:
            return
        if not self._roster_configured:
            self._emit_error("Roster not configured.")
            return
        if not self._state.can_download_all:
            self._emit_error(
                "Configure term, section, course, and consent quiz before downloading all."
            )
            return

        term = self._state.selected_term
        class_number = self._state.class_number.strip()
        if not class_number and self._state.sections and self._state.selected_section_idx >= 0:
            class_number = self._state.sections[self._state.selected_section_idx].class_number
        if not class_number:
            self._emit_error("Provide a class number directly, or search for sections first.")
            return

        try:
            course_id = int(self._state.selected_course_id.strip())
            consent_quiz_id = int(self._state.selected_consent_quiz_id.strip())
        except ValueError:
            self._emit_error("Invalid course or consent quiz ID.")
            return

        assignment_id: int | None = None
        assignment_id_str = self._state.assignment_id.strip()
        if assignment_id_str:
            try:
                assignment_id = int(assignment_id_str)
            except ValueError:
                self._emit_error("Invalid assignment ID.")
                return

        self._set_busy("Downloading all data...")
        output_dir = self._resolve_output_dir()
        roster_client = self._client
        canvas_client = self._canvas_client

        def work() -> _DownloadAllResult:
            successes: list[str] = []
            failures: list[str] = []
            last_path: Path | None = None

            try:
                roster_client.authenticate()
                try:
                    roster_path = output_dir / f"roster_{term}_{class_number}.csv"
                    download_roster_to_file(
                        roster_client,
                        RosterRequest(term=term, class_number=class_number),
                        roster_path,
                    )
                    successes.append("Roster")
                    last_path = roster_path
                finally:
                    roster_client.close()
            except Exception as exc:  # noqa: BLE001
                failures.append(f"Roster: {exc}")

            try:
                gb_result = DownloadGradebookUseCase(canvas_client).execute(
                    DownloadGradebookRequest(course_id=course_id, output_dir=output_dir)
                )
                successes.append("Gradebook")
                last_path = gb_result.saved_path
            except Exception as exc:  # noqa: BLE001
                failures.append(f"Gradebook: {exc}")

            try:
                gs_result = DownloadGradescopeSubmissionsUseCase().execute(
                    DownloadGradescopeSubmissionsRequest(course_id=course_id, output_dir=output_dir)
                )
                successes.append("Gradescope Submissions")
                last_path = gs_result.saved_path
            except Exception as exc:  # noqa: BLE001
                failures.append(f"Gradescope Submissions: {exc}")

            try:
                consent_result = DownloadConsentFormUseCase(canvas_client).execute(
                    DownloadConsentFormRequest(
                        course_id=course_id, quiz_id=consent_quiz_id, output_dir=output_dir
                    )
                )
                successes.append("Consent Form")
                last_path = consent_result.saved_path
            except Exception as exc:  # noqa: BLE001
                failures.append(f"Consent Form: {exc}")

            if assignment_id is not None:
                try:
                    rubric_result = DownloadRubricAssessmentUseCase(canvas_client).execute(
                        DownloadRubricAssessmentRequest(
                            course_id=course_id,
                            assignment_id=assignment_id,
                            output_dir=output_dir,
                        )
                    )
                    successes.append("Rubric Assessment")
                    last_path = rubric_result.saved_path
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"Rubric Assessment: {exc}")

            return _DownloadAllResult(
                successes=tuple(successes),
                failures=tuple(failures),
                last_saved_path=last_path,
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
        else:
            status = Status.NOMINAL
            message = f"All downloads complete: {', '.join(res.successes)}."

        last_saved = (
            str(res.last_saved_path) if res.last_saved_path else self._state.last_saved_path
        )
        self._state = replace(
            self._state,
            is_busy=False,
            status=status,
            message=message,
            last_saved_path=last_saved,
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
