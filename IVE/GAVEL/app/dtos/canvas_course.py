from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanvasCourse:
    id: int
    name: str
    course_code: str | None = None


@dataclass(frozen=True)
class CanvasModule:
    id: int
    name: str


@dataclass(frozen=True)
class CanvasCourseData:
    course: CanvasCourse
    modules: list[CanvasModule]
