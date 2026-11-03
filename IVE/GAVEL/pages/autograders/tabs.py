import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QLabel, QWidget, QMenu, QVBoxLayout, QComboBox, QPushButton, QHBoxLayout, QCheckBox, \
    QApplication, QStyle, QPlainTextEdit

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.section_card import SectionCard

from GAVEL.infra.autograders.parallel_autograder_client import autograde_submissions_folder, Language

TEMP_PATH = Path("C:/Users\dcgul\Downloads\GAVEL\courses\ser222_25sc_12345\original/submissions/")
AUTOGRADERS_TEMP = Path("GAVEL/autograders/")
COURSES_TEMP = Path("C:/Users\dcgul\Downloads\GAVEL\courses/")


def get_assignment_subfolders(folder: Path) -> list[str]:
    if not folder.exists():
        return []

    if not folder.is_dir():
        return []

    return [
        p.name
        for p in folder.iterdir()
        if p.is_dir() and p.name != "_unmatched"
    ]

class RunAutogradersTab(ScrollableTab):
    def __init__(self, theme: ThemeContext) -> None:
        super().__init__(theme)

        self._theme = theme

        self.course_combo: QComboBox | None = None
        self.assignment_combo: QComboBox | None = None

        self.autograders_card: SectionCard | None = None
        self.autograder_checkboxes: list[QCheckBox] = []

        self.add_section(self._build_course_select_dropdown(COURSES_TEMP))
        self.add_section(self._build_assignments_dropdown(TEMP_PATH))
        self.add_section(self._build_available_autograders_dropdown())

        self.run_btn = QPushButton("Run")

        icon = QApplication.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaPlay
        )

        self.run_btn.setIcon(icon)
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run_autograders)
        self.add_section(self.run_btn)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        log_card = SectionCard(self._theme, "Execution Log")
        log_card.add_row(self.log_output)

        self.add_section(log_card)

        self.add_stretch()

    # building a stub description card

    def _build_description_card(self) -> QWidget:
        card = SectionCard(self._theme, "Run Autograder(s)")
        badge = QLabel("(early alpha)")
        badge.setProperty("role", "text_muted")
        card.add_title_suffix(badge)
        description = QLabel("What a mess this page is!..")
        description.setWordWrap(True)
        card.add_row(description)
        return card

    # this is the dropdown menu to select a course, later to be replaced by a global course select

    def _build_course_select_dropdown(self, courses_folder: Path) -> QWidget:
        card = SectionCard(self._theme, "Select Course:")

        self.course_combo = QComboBox()
        self.course_combo.addItems(get_assignment_subfolders(courses_folder))
        self.course_combo.setCurrentIndex(-1)

        self.course_combo.currentTextChanged.connect(
            self._on_course_selected
        )

        card.add_row(self.course_combo)
        return card

    # this is the assignments dropdown which will populate upon selection of a course

    def _build_assignments_dropdown(self, assignments_folder: Path) -> QWidget:
        card = SectionCard(self._theme, "Select Assignment:")

        self.assignment_combo = QComboBox()
        self.assignment_combo.setProperty("role", "dropdown")

        self.assignment_combo.setCurrentIndex(-1)

        self.assignment_combo.currentTextChanged.connect(
            self._on_assignment_selected
        )

        card.add_row(self.assignment_combo)
        return card


    # this checkbox field populates upon selection of an assignment

    def _build_available_autograders_dropdown(self) -> QWidget:
        self.autograders_card = SectionCard(
            self._theme,
            "Select Autograder(s):"
        )

        # self.autograders_card.set_subtitle("Autograders")

        return self.autograders_card

    # this method updates the available assignments and clears the autograders

    def _on_course_selected(self, course: str) -> None:
        if not course:
            return

        assignment_folder = COURSES_TEMP / course / "original/submissions"

        assignments = get_assignment_subfolders(
            assignment_folder
        )

        self.assignment_combo.clear()
        self.assignment_combo.addItems(assignments)
        self.assignment_combo.setCurrentIndex(-1)
        self._update_run_button_state()

        self._clear_autograders()

    #TODO: better logic for extracting the course name

    # this method extracts the course name and calls to populate the autograder checkboxes

    def _on_assignment_selected(self, assignment: str) -> None:
        course = self.course_combo.currentText()
        course_name = course.split("_")[0]
        if not course or not assignment:
            return

        autograder_folder = (
            AUTOGRADERS_TEMP
            / course_name
            / assignment
        )

        self._update_run_button_state()

        self._populate_autograders(autograder_folder)

    # this
    def _populate_autograders(
            self,
            autograders_folder: Path
    ) -> None:

        self._clear_autograders()

        for name in get_assignment_subfolders(
                autograders_folder
        ):
            cb = QCheckBox(name)
            cb.stateChanged.connect(self._update_run_button_state)

            self.autograder_checkboxes.append(cb)
            self.autograders_card.add_row(cb)

    def _clear_autograders(self) -> None:
        while self.autograder_checkboxes:
            cb = self.autograder_checkboxes.pop()

            self.autograders_card.body_layout.removeWidget(cb)
            cb.deleteLater()

    def _run_autograders(self):
        course = self.course_combo.currentText()
        autograde_submissions_folder(
            Language.JAVA, input_folder="C:/Users\dcgul\OneDrive\Desktop\SER401 Project\SER401_Team5\data_original/10_24_autograder_test",
            output_folder="C:/Users\dcgul\OneDrive\Desktop\SER401 Project\SER401_Team5\data_original/autograder_test_output",
            autograder_folder_arg="C:/Users\dcgul\OneDrive\Desktop\SER401 Project\SER401_Team5\data_original/10_22_autograder")

    def _can_run(self) -> bool:
        course_selected = bool(self.course_combo.currentText())
        assignment_selected = bool(self.assignment_combo.currentText())
        autograder_selected = any(
            cb.isChecked() for cb in self.autograder_checkboxes
        )

        if not course_selected:
            self.run_btn.setToolTip("Select a course")
        elif not assignment_selected:
            self.run_btn.setToolTip("Select an assignment")
        elif not autograder_selected:
            self.run_btn.setToolTip("Select at least one autograder")
        else:
            self.run_btn.setToolTip("")
        return course_selected and assignment_selected and autograder_selected

    def _update_run_button_state(self) -> None:
        self.run_btn.setEnabled(self._can_run())

class AutograderWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def run(self):
        try:
            autograde_submissions_folder(
                Language.JAVA,
                input_folder=...,
                output_folder=...,
                autograder_folder_arg=...
            )
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


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

