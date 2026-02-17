from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class CanvasCourse:
    id: int
    name: str
    course_code: Optional[str] = None


@dataclass(frozen=True)
class CanvasModule:
    id: int
    name: str


@dataclass(frozen=True)
class CanvasCourseData:
    course: CanvasCourse
    modules: List[CanvasModule]
