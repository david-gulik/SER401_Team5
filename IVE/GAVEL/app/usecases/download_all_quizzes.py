from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.canvas_client import (
    CanvasClient,
    QuizReportUnavailableError,
)
from GAVEL.app.progress import ProgressCallback, report
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.recording import (
    ArtifactExistsError,
    guard_not_downloaded,
    note_course,
    record,
)

log = logging.getLogger(__name__)

PROGRESS_LABEL = "Downloading quizzes"


@dataclass(frozen=True)
class DownloadAllQuizzesRequest:
    course_id: int
    folder: CourseFolder
    overwrite: bool = False


@dataclass(frozen=True)
class QuizDownloadOutcome:
    quiz_id: int
    quiz_name: str
    saved_path: Path | None
    skipped_reason: str | None
    error: str | None
    # A skip because the CSV is already in the folder, not because Canvas had no report.
    already_downloaded: bool = False

    @property
    def status(self) -> str:
        if self.error is not None:
            return "failed"
        if self.skipped_reason is not None:
            return "skipped"
        return "succeeded"


@dataclass(frozen=True)
class DownloadAllQuizzesResult:
    outcomes: tuple[QuizDownloadOutcome, ...]

    @property
    def succeeded(self) -> tuple[QuizDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "succeeded")

    @property
    def failed(self) -> tuple[QuizDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "failed")

    @property
    def skipped(self) -> tuple[QuizDownloadOutcome, ...]:
        return tuple(o for o in self.outcomes if o.status == "skipped")

    @property
    def already_downloaded(self) -> tuple[QuizDownloadOutcome, ...]:
        """The skipped quizzes whose CSV was already in the folder."""
        return tuple(o for o in self.skipped if o.already_downloaded)


class DownloadAllQuizzesUseCase:
    """Saves every quiz's student analysis export as ``original/quizzes/<quiz id>.csv``.

    The quiz title goes on the manifest entry's ``label`` so the folder stays
    keyed by id. A quiz already in the folder is skipped, not overwritten.
    ``on_progress`` hears once the quiz list is known and again as each quiz
    finishes, whether it was saved, skipped, or failed.
    """

    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(
        self,
        request: DownloadAllQuizzesRequest,
        on_progress: ProgressCallback | None = None,
    ) -> DownloadAllQuizzesResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        tree = request.folder.original
        log.info("Listing quizzes for course %s", request.course_id)
        quizzes = self._canvas_client.list_quizzes(request.course_id)
        total = len(quizzes)
        log.info("Found %d quiz(zes) for course %s", total, request.course_id)
        report(on_progress, PROGRESS_LABEL, 0, total)

        outcomes = []
        for index, quiz in enumerate(quizzes, start=1):
            path = tree.quiz_csv(quiz.id)
            log.info("Quiz %d of %d: '%s' (id %s)", index, total, quiz.name, quiz.id)
            try:
                guard_not_downloaded(request.folder, path, request.overwrite)
                csv_bytes = self._canvas_client.fetch_quiz_student_analysis(
                    request.course_id,
                    quiz.id,
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(csv_bytes)
                record(request.folder, "quiz", path, source_id=quiz.id, label=quiz.name)

                outcomes.append(
                    QuizDownloadOutcome(
                        quiz_id=quiz.id,
                        quiz_name=quiz.name,
                        saved_path=path,
                        skipped_reason=None,
                        error=None,
                    )
                )

            except ArtifactExistsError as exc:
                outcomes.append(
                    QuizDownloadOutcome(
                        quiz_id=quiz.id,
                        quiz_name=quiz.name,
                        saved_path=path,
                        skipped_reason=str(exc),
                        error=None,
                        already_downloaded=True,
                    )
                )

            except QuizReportUnavailableError as exc:
                outcomes.append(
                    QuizDownloadOutcome(
                        quiz_id=quiz.id,
                        quiz_name=quiz.name,
                        saved_path=None,
                        skipped_reason=str(exc),
                        error=None,
                    )
                )

            except Exception as exc:  # noqa: BLE001
                outcomes.append(
                    QuizDownloadOutcome(
                        quiz_id=quiz.id,
                        quiz_name=quiz.name,
                        saved_path=None,
                        skipped_reason=None,
                        error=str(exc),
                    )
                )

            _log_outcome(outcomes[-1], index, total)
            report(on_progress, PROGRESS_LABEL, index, total, quiz.name)

        if any(o.status == "succeeded" for o in outcomes):
            note_course(request.folder, canvas_course_id=request.course_id)

        result = DownloadAllQuizzesResult(outcomes=tuple(outcomes))
        log.info(
            "Quiz reports for course %s done: %d saved, %d already downloaded, "
            "%d skipped, %d failed",
            request.course_id,
            len(result.succeeded),
            len(result.already_downloaded),
            len(result.skipped) - len(result.already_downloaded),
            len(result.failed),
        )
        return result


def _log_outcome(outcome: QuizDownloadOutcome, index: int, total: int) -> None:
    prefix = f"Quiz {index} of {total} '{outcome.quiz_name}'"
    if outcome.status == "succeeded":
        log.info("%s: saved to %s", prefix, outcome.saved_path)
    elif outcome.already_downloaded:
        log.info("%s: already downloaded at %s", prefix, outcome.saved_path)
    elif outcome.status == "skipped":
        log.warning("%s: skipped, %s", prefix, outcome.skipped_reason)
    else:
        log.error("%s: failed, %s", prefix, outcome.error)
