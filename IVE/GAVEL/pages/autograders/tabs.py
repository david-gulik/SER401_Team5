from pathlib import Path

from PyQt6.QtWidgets import QLabel, QWidget, QMenu, QVBoxLayout, QComboBox, QPushButton, QHBoxLayout, QCheckBox

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard

TEMP_PATH = Path("C:/Users\dcgul\Downloads\GAVEL\courses\ser222_25sc_12345\original/submissions/")
AUTOGRADERS_TEMP = Path("GAVEL/autograders/SER222")
COURSES_TEMP = Path("C:/Users\dcgul\Downloads\GAVEL\courses/")

def get_assignment_subfolders(folder: Path):
    return [p.name for p in folder.iterdir() if p.is_dir() and p.name != "_unmatched"]


class RunAutogradersTab(ScrollableTab):
    def __init__(self, theme: ThemeContext) -> None:
        super().__init__(theme)
        self._theme = theme

        # self.add_section(self._build_description_card())
        self.add_section(self._build_course_select_dropdown(COURSES_TEMP))
        self.add_section(self._build_assignments_dropdown(TEMP_PATH))
        self.add_section(self._build_available_autograders_dropdown(AUTOGRADERS_TEMP))
        self.add_stretch()

    def _build_description_card(self) -> QWidget:
        card = SectionCard(self._theme, "Run Autograder(s)")
        badge = QLabel("(early alpha)")
        badge.setProperty("role", "text_muted")
        card.add_title_suffix(badge)
        description = QLabel("What a mess this page is!..")
        description.setWordWrap(True)
        card.add_row(description)
        return card

    def _build_course_select_dropdown(self, courses_folder: Path) -> QWidget:
        card = SectionCard(self._theme, "Select Course(s):")
        combo = QComboBox()
        combo.addItems(get_assignment_subfolders(courses_folder))
        card.add_row(combo)
        return card

    def _build_assignments_dropdown(self, assignments_folder: Path) -> QWidget:
        card = SectionCard(self._theme, "Select Assignment:")
        combo = QComboBox()
        combo.setProperty("role", "dropdown")
        combo.addItems(get_assignment_subfolders(assignments_folder))
        card.add_row(combo)
        return card

    def _build_available_autograders_dropdown(self, autograders_folder: Path) -> QWidget:
        card = SectionCard(self._theme, "Select Autograder(s):")
        card.set_subtitle("Autograders")
        checkboxes: list[QCheckBox] = []

        for autograder in get_assignment_subfolders(autograders_folder):
            cb = QCheckBox(autograder)
            checkboxes.append(cb)
            card.add_row(cb)

        return card



class AutogradersDiagnosticsPage(ScrollableTab):
    def __init__(self, theme: ThemeContext) -> None:
        super().__init__(theme)
        self._theme = theme

        self.add_section(self._build_description_card())
        self.add_stretch()

    def _build_description_card(self) -> QWidget:
        card = SectionCard(self._theme, "Autograders Diagnostics")
        description = QLabel("This is just a stub right now...")
        description.setWordWrap(True)
        card.add_row(description)
        return card
