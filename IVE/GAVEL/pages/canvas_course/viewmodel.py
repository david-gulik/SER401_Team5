from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from GAVEL.app.usecases.canvas_download_course import (
    DownloadCourseDataRequest,
    DownloadCourseDataUseCase,
)
from GAVEL.core.status import Status
from GAVEL.services.logger import AppLogger


@dataclass(frozen=True)
class CanvasCourseUiState:
    course_id: str
    is_busy: bool
    status: Status
    message: str
    last_saved_path: Optional[str]


@dataclass(frozen=True)
class ShowError:
    message: str


@dataclass(frozen=True)
class ShowInfo:
    message: str


class CanvasCourseViewModel(QObject):
    state_changed = pyqtSignal(object)  # CanvasCourseUiState
    event_raised = pyqtSignal(object)  # ShowError | ShowInfo

    def __init__(
        self,
        use_case: DownloadCourseDataUseCase,
        default_output_dir: Path,
        logger: AppLogger,
        canvas_configured: bool,
    ) -> None:
        super().__init__()
        self._use_case = use_case
        self._output_dir = default_output_dir
        self._logger = logger
        self._canvas_configured = canvas_configured

        initial_message = "Enter a Canvas course ID to download."
        initial_status = Status.UNKNOWN
        if not self._canvas_configured:
            initial_message = "Canvas not configured"
            initial_status = Status.CRITICAL

        self._state = CanvasCourseUiState(
            course_id="",
            is_busy=False,
            status=initial_status,
            message=initial_message,
            last_saved_path=None,
        )

    def get_state(self) -> CanvasCourseUiState:
        return self._state

    def set_course_id(self, value: str) -> None:
        text = value.strip()
        if text == self._state.course_id:
            return
        self._state = replace(self._state, course_id=text)
        self.state_changed.emit(self._state)

    def download_course(self) -> None:
        if self._state.is_busy:
            return
        if not self._canvas_configured:
            self._emit_error("Canvas not configured")
            return
        if not self._state.course_id:
            self._emit_error("Course ID is required.")
            return
        try:
            course_id = int(self._state.course_id)
        except ValueError:
            self._emit_error("Course ID must be a number.")
            return

        self._set_busy(Status.WARNING, "Downloading course data...")

        try:
            request = DownloadCourseDataRequest(course_id=course_id, output_dir=self._output_dir)
            result = self._use_case.execute(request)
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Canvas download failed: {exc}")
            self._set_idle(Status.CRITICAL, str(exc), None)
            self.event_raised.emit(ShowError(str(exc)))
            return

        self._set_idle(Status.NOMINAL, result.message, str(result.saved_path))
        self.event_raised.emit(ShowInfo(result.message))

    def _set_busy(self, status: Status, message: str) -> None:
        self._state = replace(
            self._state,
            is_busy=True,
            status=status,
            message=message,
        )
        self.state_changed.emit(self._state)

    def _set_idle(self, status: Status, message: str, saved_path: Optional[str]) -> None:
        self._state = replace(
            self._state,
            is_busy=False,
            status=status,
            message=message,
            last_saved_path=saved_path,
        )
        self.state_changed.emit(self._state)

    def _emit_error(self, message: str) -> None:
        self._set_idle(Status.CRITICAL, message, self._state.last_saved_path)
        self.event_raised.emit(ShowError(message))
