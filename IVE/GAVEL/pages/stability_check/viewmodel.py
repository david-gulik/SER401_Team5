"""State behind the Stability Check page: what to run, how it is going, what it found."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from GAVEL.app.dtos.stability import StabilityReport
from GAVEL.app.ports.autograder_runner import AutograderRunner
from GAVEL.app.progress import DownloadProgress
from GAVEL.app.usecases.check_stability import CheckStabilityRequest, CheckStabilityUseCase
from GAVEL.app.usecases.proxy_grade.mappings.registry import MAPPINGS
from GAVEL.app.workspace.autograders import AutograderOption, ensure_extracted, list_autograders
from GAVEL.app.workspace.dataset import CourseDataset, DatasetReaders, MissingArtifactError
from GAVEL.app.workspace.layout import CourseFolder, Workspace
from GAVEL.app.workspace.manifest import ManifestError
from GAVEL.app.workspace.stability_reports import ReportSummary, StabilityReportStore
from GAVEL.core.background import BackgroundRunner, run_in_background

DEFAULT_RUNS = 10
DEFAULT_TIMEOUT_MINUTES = 5
MIN_RUNS = 2
MAX_RUNS = 100
MAX_TIMEOUT_MINUTES = 60


def default_workers() -> int:
    """Logical CPUs minus two, so the app stays responsive; never below one."""
    return max(1, (os.cpu_count() or 2) - 2)


class Phase(Enum):
    SET_UP = "set_up"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class ModuleOption:
    """A module with extracted submissions to run against."""

    module_number: int
    label: str
    submission_dirs: tuple[Path, ...]

    @property
    def submissions(self) -> int:
        return len(self.submission_dirs)


@dataclass(frozen=True)
class StabilityUiState:
    course: CourseFolder | None = None
    course_error: str | None = None
    modules: tuple[ModuleOption, ...] = ()
    module: ModuleOption | None = None
    autograders: tuple[AutograderOption, ...] = ()
    autograder: AutograderOption | None = None
    # Earlier checks of the selected assignment with the selected autograder, newest first.
    previous: tuple[ReportSummary, ...] = ()
    runs: int = DEFAULT_RUNS
    workers: int = field(default_factory=default_workers)
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES
    phase: Phase = Phase.SET_UP
    progress: DownloadProgress | None = None
    cancel_requested: bool = False
    report: StabilityReport | None = None
    saved_to: Path | None = None
    error: str | None = None

    @property
    def missing(self) -> str | None:
        """Why the check cannot start yet, or None when everything is picked."""
        if self.course is None:
            return "Choose a course"
        if self.module is None:
            return "Choose an assignment"
        if self.autograder is None:
            return "Choose an autograder"
        return None

    @property
    def executions(self) -> int:
        return self.module.submissions * self.runs if self.module is not None else 0

    @property
    def estimate(self) -> str:
        if self.module is None:
            return ""
        text = f"{self.module.submissions} submissions × {self.runs} runs = {self.executions} executions"
        pace = next(
            (p.mean_execution_seconds for p in self.previous if p.mean_execution_seconds), None
        )
        if pace is None:
            return f"{text} · no earlier check to estimate the time from"
        minutes = max(1, round(self.executions * pace / self.workers / 60))
        return f"{text} · about {minutes} min at the last check's pace, with {self.workers} workers"

    @property
    def summary(self) -> str:
        """One line naming what is being checked, for the collapsed Set up card."""
        if self.module is None or self.autograder is None:
            return ""
        return (
            f"{self.module.label} · {self.autograder.name} · "
            f"{self.module.submissions} submissions × {self.runs} runs · "
            f"{self.workers} workers · {self.timeout_minutes} min timeout"
        )


class StabilityCheckViewModel(QObject):
    state_changed = pyqtSignal(object)  # StabilityUiState
    _progress_reported = pyqtSignal(object)  # DownloadProgress, hopped onto the GUI thread

    def __init__(
        self,
        dataset_readers: DatasetReaders,
        workspace: Workspace,
        runner: AutograderRunner,
        store: StabilityReportStore | None = None,
        background: BackgroundRunner = run_in_background,
        workers: int | None = None,
    ) -> None:
        super().__init__()
        self._dataset_readers = dataset_readers
        self._workspace = workspace
        self._use_case = CheckStabilityUseCase(runner)
        self._store = store or StabilityReportStore(workspace)
        self._background = background
        self._cancel = threading.Event()
        self._course_after_run: CourseFolder | None = None
        self._state = StabilityUiState(
            workers=workers if workers is not None else default_workers()
        )
        self._progress_reported.connect(self._on_progress)

    @property
    def state(self) -> StabilityUiState:
        return self._state

    # ----- picking what to run -------------------------------------------------------------

    def select_course(self, course: CourseFolder | None) -> None:
        if self._state.phase is Phase.RUNNING:
            # The check finishes on the course it started with; the switch is applied after.
            self._course_after_run = course
            return
        modules, error = self._modules_for(course)
        self._update(
            course=course,
            course_error=error,
            modules=modules,
            module=None,
            autograders=(),
            autograder=None,
            previous=(),
            phase=Phase.SET_UP,
            progress=None,
            cancel_requested=False,
            report=None,
            saved_to=None,
            error=None,
        )

    def select_module(self, module_number: int | None) -> None:
        module = next((m for m in self._state.modules if m.module_number == module_number), None)
        autograders: tuple[AutograderOption, ...] = ()
        if module is not None and self._state.course is not None:
            autograders = list_autograders(
                self._workspace, self._state.course.key, module.module_number
            )
        self._update(module=module, autograders=autograders, autograder=None, previous=())

    def select_autograder(self, name: str | None) -> None:
        option = next((a for a in self._state.autograders if a.name == name), None)
        previous: tuple[ReportSummary, ...] = ()
        if option is not None and self._state.course is not None and self._state.module is not None:
            previous = self._store.list(
                self._state.course.key.folder_name, self._state.module.module_number, option.name
            )
        self._update(autograder=option, previous=previous)

    def set_runs(self, runs: int) -> None:
        self._update(runs=min(MAX_RUNS, max(MIN_RUNS, runs)))

    def set_workers(self, workers: int) -> None:
        self._update(workers=max(1, workers))

    def set_timeout_minutes(self, minutes: int) -> None:
        self._update(timeout_minutes=min(MAX_TIMEOUT_MINUTES, max(1, minutes)))

    # ----- running ---------------------------------------------------------------------------

    def start(self) -> None:
        state = self._state
        if state.missing is not None or state.phase is Phase.RUNNING:
            return
        assert state.course is not None and state.module is not None
        assert state.autograder is not None
        course, module, autograder = state.course, state.module, state.autograder
        key = course.key
        mapping = MAPPINGS.get(f"{key.subject.lower()}{key.catalog_number}_m{module.module_number}")
        runs, workers, timeout = state.runs, state.workers, state.timeout_minutes * 60.0

        self._cancel.clear()
        self._course_after_run = None
        self._update(
            phase=Phase.RUNNING,
            progress=None,
            cancel_requested=False,
            report=None,
            saved_to=None,
            error=None,
        )

        def work() -> tuple[StabilityReport, Path]:
            autograder_dir = ensure_extracted(
                autograder, self._workspace, key, module.module_number
            )
            request = CheckStabilityRequest(
                course=key.folder_name,
                module_number=module.module_number,
                autograder=autograder.name,
                autograder_dir=autograder_dir,
                submission_dirs=module.submission_dirs,
                runs=runs,
                workers=workers,
                timeout_seconds=timeout,
                mapping=mapping,
            )
            report = self._use_case.execute(
                request, on_progress=self._report_progress, is_cancelled=self._cancel.is_set
            )
            return report, self._store.save(report)

        self._background(work, self._on_finished, self._on_failed)

    def cancel(self) -> None:
        if self._state.phase is not Phase.RUNNING:
            return
        self._cancel.set()
        self._update(cancel_requested=True)

    def edit_settings(self) -> None:
        """Back to the Set up card; the report stays on the page until a new check starts."""
        if self._state.phase is Phase.DONE:
            self._update(phase=Phase.SET_UP)

    def open_report(self, path: Path) -> None:
        """Show a saved report as if it had just finished."""
        if self._state.phase is Phase.RUNNING:
            return
        try:
            report = self._store.load(path)
        except (OSError, ValueError, KeyError) as exc:
            self._update(phase=Phase.FAILED, error=f"Could not open {path.name}: {exc}")
            return
        self._update(phase=Phase.DONE, report=report, saved_to=Path(path), error=None)

    def _report_progress(self, progress: DownloadProgress) -> None:
        # Called on a worker thread; the signal delivers it on the GUI thread.
        self._progress_reported.emit(progress)

    def _on_progress(self, progress: object) -> None:
        if self._state.phase is Phase.RUNNING:
            self._update(progress=progress)

    def _on_finished(self, result: object) -> None:
        report, saved_to = result
        previous = self._store.list(report.course, report.module_number, report.autograder)
        self._update(phase=Phase.DONE, report=report, saved_to=saved_to, previous=previous)
        self._apply_deferred_course()

    def _on_failed(self, exc: Exception) -> None:
        self._update(phase=Phase.FAILED, error=f"{type(exc).__name__}: {exc}")
        self._apply_deferred_course()

    def _apply_deferred_course(self) -> None:
        if self._course_after_run is not None and self._course_after_run != self._state.course:
            course, self._course_after_run = self._course_after_run, None
            self.select_course(course)

    # ----- helpers ---------------------------------------------------------------------------

    def _modules_for(
        self, course: CourseFolder | None
    ) -> tuple[tuple[ModuleOption, ...], str | None]:
        if course is None:
            return (), None
        labels = self._assignment_labels(course)
        modules = []
        for module in course.anonymized.list_module_submissions():
            submission_dirs = module.submission_dirs()
            if not submission_dirs:
                continue
            number = module.module_number
            modules.append(
                ModuleOption(number, labels.get(number, f"Module {number}"), submission_dirs)
            )
        if not modules:
            return (), "No anonymized submissions in this course. Sanitize it first."
        return tuple(modules), None

    def _assignment_labels(self, course: CourseFolder) -> dict[int, str]:
        try:
            assignments = CourseDataset.anonymized(course, self._dataset_readers).assignments()
        except (MissingArtifactError, ManifestError, OSError, ValueError):
            return {}
        labels: dict[int, str] = {}
        for entry in assignments:
            if entry.module_number is not None:
                labels.setdefault(entry.module_number, entry.name)
        return labels

    def _update(self, **changes: object) -> None:
        self._state = replace(self._state, **changes)
        self.state_changed.emit(self._state)
