from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.ports.canvas_client import (
    CanvasClient,
    QuizReportUnavailableError,
)


@dataclass(frozen=True)
class DownloadAllQuizzesRequest:
    course_id: int
    output_dir: Path


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
    def __init__(self, canvas_client: CanvasClient) -> None:
        self._canvas_client = canvas_client

    def execute(
        self,
        request: DownloadAllQuizzesRequest,
    ) -> DownloadAllQuizzesResult:
        if request.course_id <= 0:
            raise ValueError("course_id must be greater than zero")

        request.output_dir.mkdir(parents=True, exist_ok=True)

        quizzes = self._canvas_client.list_quizzes(request.course_id)

        outcomes = []

        for quiz in quizzes:
            try:
                csv_bytes = self._canvas_client.fetch_quiz_student_analysis(
                    request.course_id,
                    quiz.id,
                )

                safe_name = "".join(
                    c if c.isalnum() or c in ("-", "_") else "_" for c in quiz.name
                ).strip("_")

                if not safe_name:
                    safe_name = "quiz"

                path = request.output_dir / f"{safe_name}_{quiz.id}.csv"
                path.write_bytes(csv_bytes)

                outcomes.append(
                    QuizDownloadOutcome(
                        quiz_id=quiz.id,
                        quiz_name=quiz.name,
                        saved_path=path,
                        skipped_reason=None,
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

        return DownloadAllQuizzesResult(outcomes=tuple(outcomes))
