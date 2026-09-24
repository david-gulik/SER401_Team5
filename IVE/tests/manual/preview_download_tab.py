"""Interactive preview of the Download tab with seeded myASU and Canvas data.

Not collected by pytest (no test_ prefix). Run from the IVE folder:
    python -m tests.manual.preview_download_tab
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasCourse, CanvasQuiz
from GAVEL.app.dtos.roster import ClassSection, TermInfo
from GAVEL.pages.download.tabs import DownloadTab
from GAVEL.pages.download.viewmodel import DownloadViewModel
from GAVEL.services.logger import AppLogger
from GAVEL.theme.context import ThemeContext
from GAVEL.theme.qss_builder import build_app_qss
from GAVEL.theme.tokens import load_tokens
from tests.pages.download.fakes import FakeCanvasClient, FakeRosterClient

TERMS = [
    TermInfo("2271", "Spring 2027"),
    TermInfo("2267", "Fall 2026", default=True),
    TermInfo("2264", "Summer 2026"),
    TermInfo("2261", "Spring 2026"),
]

# Class numbers 87275, 37789, 75307 and 88213 match the Canvas codes below.
SECTIONS = [
    ClassSection("87275", "SER", "402", "Computing Capstone II", "Acuna", "TTh 12:00PM", "C"),
    ClassSection("12345", "SER", "402", "Computing Capstone II", "Gary", "MW 3:00PM", "C"),
    ClassSection("37789", "SER", "401", "Computing Capstone I", "Acuna", "TTh 12:00PM", "C"),
    ClassSection("11111", "SER", "401", "Computing Capstone I", "Gary", "MW 3:00PM", "C"),
    ClassSection("75307", "CSE", "475", "Found of Machine Learning", "Li", "MW 1:30PM", "C"),
    ClassSection("88213", "SER", "475", "Found of Machine Learning", "Li", "MW 1:30PM", "C"),
    ClassSection("22222", "CSE", "475", "Found of Machine Learning", "Wu", "TTh 9:00AM", "C"),
]

COURSES = [
    CanvasCourse(
        273116, "SER 402: Computing Capstone II (2026 Fall C)", "2026FallC-X-SER402-87275"
    ),
    CanvasCourse(
        250417, "SER 401: Computing Capstone I (2026 Spring C)", "2026SpringC-X-SER401-37789"
    ),
    CanvasCourse(
        266960, "CSE/SER 475: Found of Machine Learning", "2026FallC-X-CSE475-SER475-75307-88213"
    ),
    CanvasCourse(272202, "CSE 355 (Online, Fall 2026)", "2026FallC-X-CSE355-77621"),
    CanvasCourse(253450, "TRN-2026Spring-IVECapstone", "TRN-2026Spring-ivecapstone"),
]
QUIZZES = [CanvasQuiz(1960789, "Research Consent Form"), CanvasQuiz(1960790, "Syllabus Quiz")]
ASSIGNMENTS = [
    CanvasAssignment(7216983, "Sprint 1 Retrospective"),
    CanvasAssignment(7216990, "Sprint 2 Retrospective"),
    CanvasAssignment(7216999, "Attendance", has_rubric=False),
]


class SeededRosterClient(FakeRosterClient):
    """Filters the canned sections by subject and catalog like the real search."""

    def find_sections(self, term: str, subject: str, catalog_number: str) -> Sequence[ClassSection]:
        self.section_queries.append((term, subject, catalog_number))
        return [
            s
            for s in self.sections
            if s.subject == subject.upper() and s.catalog_number == catalog_number
        ]


class SeededCanvasClient(FakeCanvasClient):
    """Gradebook and consent downloads succeed; rubric and Gradescope still fail."""

    def fetch_gradebook_csv(self, course_id: int) -> bytes:
        return b"Student,ID,SIS Login ID,Section\nAda Lovelace,1000000001,alovelac,87275\n"

    def fetch_quiz_student_analysis(self, course_id: int, quiz_id: int) -> bytes:
        return b"name,sis_id,attempt,1.0: I consent\nAda Lovelace,1000000001,1,Yes\n"


def main() -> None:
    os.environ.setdefault("CANVAS_TOKEN", "preview-token")
    output_dir = Path(tempfile.mkdtemp(prefix="gavel-preview-"))
    print(f"[preview] downloads go to {output_dir}")

    app = QApplication(sys.argv)
    tokens = load_tokens(
        Path(__file__).resolve().parents[2] / "GAVEL" / "theme" / "tokens_dark.json"
    )
    app.setStyleSheet(build_app_qss(tokens))
    theme = ThemeContext(tokens=tokens)

    vm = DownloadViewModel(
        roster_client=SeededRosterClient(terms=TERMS, sections=SECTIONS),
        canvas_client=SeededCanvasClient(courses=COURSES, quizzes=QUIZZES, assignments=ASSIGNMENTS),
        default_output_dir=output_dir,
        logger=AppLogger("preview"),
        roster_configured=True,
    )
    tab = DownloadTab(theme, vm)
    tab.setWindowTitle("Download tab preview (seeded data, no network)")
    tab.resize(960, 900)
    tab.show()
    if "--smoke" in sys.argv:
        QTimer.singleShot(1500, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
