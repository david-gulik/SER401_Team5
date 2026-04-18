from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from PyQt6.QtCore import QObject, pyqtSignal

from GAVEL.app.dtos.canvas_course import CanvasCourse
from GAVEL.app.dtos.roster import ClassSection, RosterRequest, TermInfo
from GAVEL.app.ports.canvas_client import CanvasClient
from GAVEL.app.ports.roster_client import RosterClient
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
    courses: Sequence[CanvasCourse] = ()
    sections: Sequence[ClassSection] = ()
    selected_section_idx: int = -1
    selected_course_id: str = ""
    selected_consent_quiz_idx: int = -1
    is_busy: bool = False
    status: Status = Status.UNKNOWN
    message: str = "Enter search criteria or a class number."
    last_saved_path: str | None = None

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
        return bool(self.selected_course_id) and self.selected_consent_quiz_idx >= 0

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


@dataclass(frozen=True)
class ShowError:
    message: str


@dataclass(frozen=True)
class ShowInfo:
    message: str


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
        self._output_dir = default_output_dir
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
        self._state = replace(self._state, selected_course_id=text)
        self.state_changed.emit(self._state)
        self._logger.info(f"Selected course ID set to {text}")

    def set_selected_consent_quiz(self, index: int) -> None:
        if index == self._state.selected_consent_quiz_idx:
            return
        self._state = replace(self._state, selected_consent_quiz_idx=index)
        self.state_changed.emit(self._state)
        self._logger.info(f"Selected consent quiz index set to {index}")

    # Actions

    def load_terms(self) -> None:
        if self._state.is_busy or not self._roster_configured:
            return
        self._set_busy("Loading terms...")
        try:
            terms = self._client.list_terms()
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Failed to load terms: {exc}")
            self._set_idle(Status.CRITICAL, str(exc))
            return

        default_term = ""
        for t in terms:
            if t.default:
                default_term = t.code
                break

        self._state = replace(
            self._state,
            terms=terms,
            selected_term=default_term,
            is_busy=False,
            status=Status.NOMINAL,
            message=f"Loaded {len(terms)} terms.",
        )
        self.state_changed.emit(self._state)

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
        try:
            sections = self._client.find_sections(
                self._state.selected_term,
                self._state.subject,
                self._state.catalog_number,
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Section lookup failed: {exc}")
            self._set_idle(Status.CRITICAL, str(exc))
            self.event_raised.emit(ShowError(str(exc)))
            return

        if not sections:
            self._set_idle(Status.WARNING, "No sections found.")
            return

        self._state = replace(
            self._state,
            sections=sections,
            selected_section_idx=0,
            is_busy=False,
            status=Status.NOMINAL,
            message=f"Found {len(sections)} section(s).",
        )
        self.state_changed.emit(self._state)

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

        filename = f"roster_{request.term}_{class_number}.csv"
        out_path = self._output_dir / filename

        try:
            self._client.authenticate()
            download_roster_to_file(self._client, request, out_path)
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Roster download failed: {exc}")
            self._set_idle(Status.CRITICAL, str(exc))
            self.event_raised.emit(ShowError(str(exc)))
            return
        finally:
            self._client.close()

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
        self._state = replace(
            self._state,
            courses=courses,
            is_busy=False,
            status=Status.NOMINAL,
            message=f"Loaded {len(courses)} course(s).",
        )
        self.state_changed.emit(self._state)

    def recheck(self) -> None:
        load_dotenv(find_dotenv(usecwd=True), override=True)
        self.state_changed.emit(self._state)

    # Helpers

    def _set_busy(self, message: str) -> None:
        self._state = replace(self._state, is_busy=True, status=Status.WARNING, message=message)
        self.state_changed.emit(self._state)

    def _set_idle(self, status: Status, message: str) -> None:
        self._state = replace(self._state, is_busy=False, status=status, message=message)
        self.state_changed.emit(self._state)

    def _emit_error(self, message: str) -> None:
        self._set_idle(Status.CRITICAL, message)
        self.event_raised.emit(ShowError(message))
