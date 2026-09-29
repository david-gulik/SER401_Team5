from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.canvas_client import (
    CanvasClient,
    QuizReportUnavailableError,
)
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.recording import (
    ArtifactExistsError,
    guard_not_downloaded,
    note_course,
    record,
)


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


class DownloadAllQuizzesUseCase:
    """Saves every quiz's student analysis export as ``original/quizzes/<quiz id>.csv``.

    The quiz title goes on the manifest entry's ``label`` so the folder stays
    keyed by id. A quiz already in the folder is skipped, not overwritten.
    """

    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(
        self,
        request: DownloadAllQuizzesRequest,
    ) -> DownloadAllQuizzesResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        tree = request.folder.original
        quizzes = self._canvas_client.list_quizzes(request.course_id)

        outcomes = []
        for quiz in quizzes:
            path = tree.quiz_csv(quiz.id)
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

        if any(o.status == "succeeded" for o in outcomes):
            note_course(request.folder, canvas_course_id=request.course_id)

        return DownloadAllQuizzesResult(outcomes=tuple(outcomes))
