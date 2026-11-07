from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanvasCourse:
    id: int
    name: str
    course_code: str | None = None
    # IANA zone name, e.g. "America/Phoenix"; the course's local time for due dates.
    time_zone: str | None = None
    start_at: str | None = None
    end_at: str | None = None


@dataclass(frozen=True)
class CanvasModule:
    id: int
    name: str
    position: int | None = None
    unlock_at: str | None = None


@dataclass(frozen=True)
class CanvasCourseData:
    course: CanvasCourse
    modules: list[CanvasModule]


@dataclass(frozen=True)
class CanvasQuiz:
    """A Canvas quiz. Timestamps are ISO 8601 with a UTC offset; None means
    Canvas has no value."""

    id: int
    name: str
    due_at: str | None = None
    points_possible: float | None = None
    unlock_at: str | None = None
    lock_at: str | None = None
    # "assignment", "practice_quiz", "graded_survey" or "survey".
    quiz_type: str | None = None
    # The assignment (and gradebook column) behind a graded quiz.
    assignment_id: int | None = None
    # -1 means unlimited.
    allowed_attempts: int | None = None
    # Minutes; None means no time limit.
    time_limit: int | None = None
    question_count: int | None = None
    published: bool | None = None


@dataclass(frozen=True)
class CanvasAssignment:
    """A Canvas assignment. Timestamps are ISO 8601 with a UTC offset; None
    means Canvas has no value."""

    id: int
    name: str
    has_rubric: bool = True
    due_at: str | None = None
    points_possible: float | None = None
    unlock_at: str | None = None
    lock_at: str | None = None
    # True when some sections or students have their own dates, which
    # ``due_at`` does not show.
    has_overrides: bool | None = None
    submission_types: tuple[str, ...] | None = None
    assignment_group_id: int | None = None
    published: bool | None = None
    omit_from_final_grade: bool | None = None
    # "points", "percent", "pass_fail", "letter_grade", "gpa_scale" or "not_graded".
    grading_type: str | None = None
