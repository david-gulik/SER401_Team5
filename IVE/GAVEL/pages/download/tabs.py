from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from GAVEL.app.dtos.canvas_course import CanvasAssignment, CanvasCourse, CanvasQuiz
from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.download.section_picker import SectionSearchPicker
from GAVEL.pages.download.viewmodel import (
    CONSENT_DOWNLOAD,
    GRADEBOOK_DOWNLOAD,
    GRADESCOPE_DOWNLOAD,
    ROSTER_DOWNLOAD,
    RUBRIC_DOWNLOAD,
    DownloadUiState,
    DownloadViewModel,
    ShowError,
    ShowInfo,
    assignment_ids_error,
    class_number_error,
    course_id_error,
    quiz_id_error,
    term_code_error,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.input_mode_toggle import (
    CheckListPicker,
    ComboPicker,
    InputMode,
    InputModeToggle,
)
from GAVEL.ui_components.layout import set_h_margins, set_spacing
from GAVEL.ui_components.section_card import SectionCard
from GAVEL.ui_components.status_pill import StatusPill
from GAVEL.ui_components.sub_panel import SubPanel


def _likely_consent_quiz(quizzes: Sequence[CanvasQuiz]) -> str:
    """Id of the first quiz whose name mentions consent, or "" if none does."""
    return next((str(q.id) for q in quizzes if "consent" in q.name.lower()), "")


def _quiz_label(quiz: CanvasQuiz) -> str:
    """Dropdown text: name and the Canvas quiz ID so it can be matched to a URL."""
    return f"{quiz.name}  ({quiz.id})"


_NO_RUBRIC_TIP = "No rubric attached — no rubric-level data will be produced for this assignment."


def _assignment_label(assignment: CanvasAssignment) -> str:
    """Check box text: name and the Canvas assignment ID so it can be matched to a URL.

    Assignments with no rubric attached are flagged so they can be seen before
    downloading; the view model skips them rather than fetching empty data.
    """
    name = assignment.name if assignment.has_rubric else f"⚠ {assignment.name}"
    return f"{name}  ({assignment.id})"


def _course_label(course: CanvasCourse) -> str:
    """Dropdown text: code, name, and the Canvas ID so it can be matched to a URL."""
    head = f"{course.course_code}  {course.name}" if course.course_code else course.name
    return f"{head}  ({course.id})"


# Suffix on a download button once that download has succeeded.
DONE_MARK = "✓"

# Canvas downloads in the order the card shows them, for the switch prompt.
_CANVAS_DOWNLOAD_ORDER = (
    GRADEBOOK_DOWNLOAD,
    CONSENT_DOWNLOAD,
    RUBRIC_DOWNLOAD,
    GRADESCOPE_DOWNLOAD,
)


class DownloadTab(ScrollableTab):
    def __init__(self, theme: ThemeContext, vm: DownloadViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm
        self._rendering = False
        self._render_pending = False
        self._reverting_course = False

        self._build_widgets()
        self._connect_signals()
        self.layout().insertWidget(0, self._busy_bar)

        self.add_section(self._build_output_path_card())
        self.add_section(self._build_myasu_card())
        self.add_section(self._build_canvas_card())
        self.add_section(self._build_download_all())
        self.add_stretch()
        status_host = QWidget()
        status_layout = QVBoxLayout(status_host)
        set_h_margins(status_layout, self._theme, 16, 8)
        status_layout.addWidget(self._build_status_card())
        self.layout().addWidget(status_host)

        self.render(self._vm.get_state())

        if self._vm.get_state().canvas_token_available:
            QTimer.singleShot(0, self._vm.load_courses)

    @property
    def course_input(self) -> InputModeToggle:
        """The single Canvas course input (picker or manual). Exposed for tests."""
        return self._course_input

    @property
    def section_input(self) -> InputModeToggle:
        """The single myASU section input (search or class number). Exposed for tests."""
        return self._section_input

    @property
    def term_input(self) -> InputModeToggle:
        """The single myASU term input (list or code). Exposed for tests."""
        return self._term_input

    @property
    def quiz_input(self) -> InputModeToggle:
        """The single consent quiz input (list or ID). Exposed for tests."""
        return self._quiz_input

    @property
    def assignment_input(self) -> InputModeToggle:
        """The single rubric assignment input (check list or IDs). Exposed for tests."""
        return self._assignment_input

    @property
    def section_warning_label(self) -> QLabel:
        """Banner shown when the roster class is not in the Canvas course. Exposed for tests."""
        return self._section_mismatch_warning

    def download_button(self, name: str) -> QPushButton:
        """The primary button for a download name such as ROSTER_DOWNLOAD. Exposed for tests."""
        return self._download_buttons[name][0]

    # ---------- Widget construction ----------

    def _build_widgets(self) -> None:
        # Busy indicator
        self._busy_bar = QProgressBar()
        self._busy_bar.setRange(0, 0)
        self._busy_bar.setTextVisible(False)
        self._busy_bar.setFixedHeight(6)
        self._busy_bar.hide()

        # Output path
        self._output_path = QLineEdit()
        self._output_path.setPlaceholderText("Enter custom output path")
        self._browse_path_btn = QPushButton("Browse…")
        self._browse_path_btn.setProperty("role", "secondary")
        self._reset_path_btn = QPushButton("Reset to Default")
        self._reset_path_btn.setProperty("role", "secondary")
        self._reset_path_btn.setToolTip(
            "Reset to the default output folder configured in Settings → Environment."
        )
        self._output_path_hint = QLabel("All downloads will be saved to this location.")
        self._output_path_hint.setProperty("role", "text_muted")
        self._output_path_hint.setWordWrap(True)

        # myASU - Step 1: one input, term list or term code, never both
        self._term_picker = ComboPicker(
            self._theme, load_text="Load Terms", empty_text="No terms loaded"
        )
        self._term_input = InputModeToggle(
            self._theme,
            "Step 1: Select Term",
            picker=self._term_picker,
            manual_field_label="Term code",
            picker_label="Choose from list",
            manual_label="Enter code",
            picker_hint="Press Load Terms to fetch the term list from myASU.",
            manual_hint="Format 2[YY][T]. T is 1 Spring, 4 Summer, 7 Fall, 9 Winter.",
            manual_placeholder="e.g. 2267",
            validator=term_code_error,
        )

        # myASU - warning banner
        self._roster_warning = QLabel(
            "Warning: ROSTER_AUTH_METHOD not set in .env file. "
            "Set it to 'selenium' or 'cookies' to use myASU roster features."
        )
        self._roster_warning.setProperty("role", "warning")
        self._roster_warning.setWordWrap(True)
        self._roster_warning.hide()

        # myASU - Step 2: one input, section search or class number, never both
        self._section_picker = SectionSearchPicker(self._theme)
        self._section_input = InputModeToggle(
            self._theme,
            "Step 2: Identify Class",
            picker=self._section_picker,
            manual_field_label="Class number",
            picker_label="Search by class",
            manual_label="Enter class number",
            picker_hint="Pick a term in Step 1, then search by subject and catalog number.",
            manual_hint="The 5-digit class number from ASU class search.",
            manual_placeholder="e.g. 12345",
            validator=class_number_error,
        )

        # myASU - Download
        self._download_roster_btn = QPushButton("Download Roster")
        self._download_roster_btn.setToolTip(
            "Requires a valid term and section to be selected above."
        )
        self._download_roster_btn.setProperty("role", "primary")

        # Canvas - warning banner
        self._canvas_warning = QLabel(
            "Warning: CANVAS_TOKEN not found in .env file. Please set it to use Canvas features."
        )
        self._canvas_warning.setProperty("role", "warning")
        self._canvas_warning.setWordWrap(True)
        self._canvas_warning.hide()
        self._canvas_recheck_btn = QPushButton("Recheck")
        self._canvas_recheck_btn.hide()

        # Canvas - course selection: one input, picker or manual, never both
        self._course_picker = ComboPicker(
            self._theme, load_text="Reload Courses", empty_text="No courses loaded"
        )
        self._course_input = InputModeToggle(
            self._theme,
            "Course",
            picker=self._course_picker,
            manual_field_label="Course ID",
            picker_label="Choose from list",
            manual_label="Enter ID",
            picker_hint="Courses load from Canvas when this page opens.",
            manual_hint="Press Enter after typing the ID to load its quizzes and assignments.",
            manual_placeholder="e.g. 213877",
            validator=course_id_error,
        )

        # Canvas - roster/course mismatch banner. Non-blocking: downloads still run.
        self._section_mismatch_warning = QLabel("")
        self._section_mismatch_warning.setProperty("role", "warning")
        self._section_mismatch_warning.setWordWrap(True)
        self._section_mismatch_warning.hide()

        # Canvas - gradebook
        self._download_gradebook_btn = QPushButton("Download Gradebook")
        self._download_gradebook_btn.setToolTip("Requires a valid course to be selected above.")
        self._download_gradebook_btn.setProperty("role", "primary")

        # Canvas - consent form: one quiz input, list or ID
        self._quiz_picker = ComboPicker(
            self._theme, load_text="Reload Quizzes", empty_text="No quizzes loaded"
        )
        self._quiz_input = InputModeToggle(
            self._theme,
            "Consent Form",
            picker=self._quiz_picker,
            manual_field_label="Quiz ID",
            picker_label="Choose from list",
            manual_label="Enter ID",
            picker_hint="Quizzes load for the selected course. The consent quiz is preselected "
            "when its name says so.",
            manual_placeholder="e.g. 1234567",
            validator=quiz_id_error,
        )
        self._download_consent_btn = QPushButton("Download Consent Form")
        self._download_consent_btn.setToolTip(
            "Requires a valid course and consent quiz to be selected above."
        )
        self._download_consent_btn.setProperty("role", "primary")

        # Canvas - Rubric Assessment: one assignment input, check list or comma-separated IDs
        self._assignment_picker = CheckListPicker(
            self._theme, load_text="Reload Assignments", empty_text="No assignments loaded"
        )
        self._assignment_input = InputModeToggle(
            self._theme,
            "Rubric Assessment",
            picker=self._assignment_picker,
            manual_field_label="Assignment IDs",
            picker_label="Choose from list",
            manual_label="Enter IDs",
            picker_hint="Assignments load for the selected course. Check every assignment "
            "whose rubric you want.",
            manual_hint="Separate multiple assignment IDs with commas.",
            manual_placeholder="e.g. 7216983, 7216990",
            validator=assignment_ids_error,
        )
        self._download_rubric_btn = QPushButton("Download Rubric Assessment")
        self._download_rubric_btn.setProperty("role", "primary")
        self._download_rubric_btn.setToolTip(
            "Requires a valid course and at least one assignment to be selected above."
        )
        self._download_all_rubric_btn = QPushButton("Download All Rubric Assessments")
        self._download_all_rubric_btn.setProperty("role", "secondary")
        self._download_all_rubric_btn.setToolTip(
            "Downloads a rubric assessment for every assignment in the selected course."
        )

        # Gradescope submissions
        self._gradescope_credentials_warning = QLabel(
            "Warning: CANVAS_USERNAME and/or CANVAS_PASSWORD not found in .env file. "
            "Please set them to use Gradescope features."
        )
        self._gradescope_credentials_warning.setProperty("role", "warning")
        self._gradescope_credentials_warning.setWordWrap(True)
        self._gradescope_credentials_warning.hide()
        self._gradescope_credentials_recheck_btn = QPushButton("Recheck")
        self._gradescope_credentials_recheck_btn.hide()
        self._download_gradescope_btn = QPushButton("Download Submissions")
        self._download_gradescope_btn.setToolTip("Requires a valid course to be selected above.")
        self._download_gradescope_btn.setProperty("role", "primary")

        # Download all
        self._download_all_btn = QPushButton("Download All")
        self._download_all_btn.setProperty("role", "primary")

        # Status
        self._status_pill = StatusPill(self._theme)
        self._message_label = QLabel("")
        self._message_label.setWordWrap(True)
        self._last_saved_label = QLabel("")
        self._last_saved_label.setWordWrap(True)
        self._last_saved_label.setProperty("role", "text_muted")
        self._last_saved_label.hide()

        # Buttons that earn a DONE_MARK once their download succeeds, with the
        # plain label to restore when the selection changes.
        self._download_buttons: dict[str, tuple[QPushButton, ...]] = {
            ROSTER_DOWNLOAD: (self._download_roster_btn,),
            GRADEBOOK_DOWNLOAD: (self._download_gradebook_btn,),
            CONSENT_DOWNLOAD: (self._download_consent_btn,),
            RUBRIC_DOWNLOAD: (self._download_rubric_btn, self._download_all_rubric_btn),
            GRADESCOPE_DOWNLOAD: (self._download_gradescope_btn,),
        }
        self._button_labels: dict[QPushButton, str] = {
            button: button.text()
            for buttons in self._download_buttons.values()
            for button in buttons
        }

    def _connect_signals(self) -> None:
        # Wired to existing view model behavior
        self._term_picker.load_requested.connect(self._vm.load_terms)
        # Single writer of the term, whichever mode produced it.
        self._term_input.value_changed.connect(self._vm.set_term)
        self._section_picker.subject_field.textChanged.connect(self._vm.set_subject)
        self._section_picker.catalog_field.textChanged.connect(self._vm.set_catalog_number)
        self._section_picker.load_requested.connect(self._vm.find_sections)
        # Single writer of the class number, whichever mode produced it.
        self._section_input.value_changed.connect(self._vm.set_class_number)
        self._download_roster_btn.clicked.connect(self._vm.download_roster)

        self._course_input.value_changed.connect(self._on_course_changed)
        self._course_input.mode_changed.connect(self._on_course_mode_changed)
        self._course_input.manual_field().editingFinished.connect(self._on_course_id_committed)
        self._course_picker.load_requested.connect(self._vm.load_courses)
        # Single writer of the consent quiz id, whichever mode produced it.
        self._quiz_input.value_changed.connect(self._vm.set_consent_quiz_id)
        self._quiz_picker.load_requested.connect(self._on_reload_quizzes)
        # Single writer of the assignment ids, whichever mode produced them.
        self._assignment_input.value_changed.connect(self._vm.set_assignment_ids)
        self._assignment_picker.load_requested.connect(self._on_reload_assignments)
        self._download_rubric_btn.clicked.connect(self._vm.download_rubric_assessment)
        self._download_all_rubric_btn.clicked.connect(self._vm.download_all_rubric_assessments)

        self._output_path.textEdited.connect(self._vm.set_output_dir)
        self._browse_path_btn.clicked.connect(self._on_browse_output_path)
        self._reset_path_btn.clicked.connect(self._vm.reset_output_dir)

        # Stubs: controls added for the new scaffold. Functionality lands later.
        self._download_gradebook_btn.clicked.connect(self._on_download_gradebook)
        self._download_consent_btn.clicked.connect(self._on_download_consent)
        self._download_gradescope_btn.clicked.connect(self._on_download_gradescope)
        self._download_all_btn.clicked.connect(self._on_download_all)

        self._canvas_recheck_btn.clicked.connect(self._vm.recheck)
        self._gradescope_credentials_recheck_btn.clicked.connect(self._vm.recheck)
        self._vm.state_changed.connect(self.render)
        self._vm.event_raised.connect(self._handle_event)

    # ---------- Card builders ----------

    def _build_output_path_card(self) -> QWidget:
        card = SectionCard(self._theme, "Global Settings")

        output_controls = SubPanel(self._theme, "Output Controls")

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(row_layout, self._theme, 8)
        row_layout.addWidget(self._output_path, 1)
        row_layout.addWidget(self._browse_path_btn)
        row_layout.addWidget(self._reset_path_btn)

        output_controls.add_widget(row)
        output_controls.add_widget(self._output_path_hint)

        card.add_row(output_controls)
        return card

    def _build_myasu_card(self) -> QWidget:
        card = SectionCard(self._theme, "myASU Class Roster")
        card.add_row(self._roster_warning)

        # Step 1: Select Term
        card.add_row(self._term_input)

        # Step 2: Identify Class
        card.add_row(self._section_input)

        card.add_row(self._download_roster_btn)
        return card

    def _build_canvas_card(self) -> QWidget:
        card = SectionCard(self._theme, "Canvas")

        warning_row = QWidget()
        warning_layout = QHBoxLayout(warning_row)
        warning_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(warning_layout, self._theme, 8)
        warning_layout.addWidget(self._canvas_warning, 1)
        warning_layout.addWidget(self._canvas_recheck_btn)
        card.add_row(warning_row)

        # Course Selection
        card.add_row(self._course_input)
        card.add_row(self._section_mismatch_warning)

        # Gradebook
        gradebook_panel = SubPanel(self._theme, "Gradebook")
        gradebook_panel.add_widget(self._download_gradebook_btn)
        card.add_row(gradebook_panel)

        # Consent Form
        self._quiz_input.add_footer(self._download_consent_btn)
        card.add_row(self._quiz_input)

        # Rubric Assessment
        self._assignment_input.add_footer(self._download_rubric_btn)
        self._assignment_input.add_footer(self._download_all_rubric_btn)
        card.add_row(self._assignment_input)

        # Gradescope Submissions
        gradescope_panel = SubPanel(self._theme, "Gradescope Submissions")

        gradescope_warning_row = QWidget()
        gradescope_warning_layout = QHBoxLayout(gradescope_warning_row)
        gradescope_warning_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(gradescope_warning_layout, self._theme, 8)
        gradescope_warning_layout.addWidget(self._gradescope_credentials_warning, 1)
        gradescope_warning_layout.addWidget(self._gradescope_credentials_recheck_btn)
        gradescope_panel.add_widget(gradescope_warning_row)

        gradescope_panel.add_widget(self._download_gradescope_btn)
        card.add_row(gradescope_panel)

        return card

    def _build_status_card(self) -> QWidget:
        card = SectionCard(self._theme, "Status")

        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)
        set_spacing(form, self._theme, 8)
        form.addRow("Status", self._status_pill)
        form.addRow("Message", self._message_label)
        form.addRow("Last Saved", self._last_saved_label)

        card.add_row(host)
        return card

    def _build_download_all(self) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._download_all_btn)
        return host

    # ---------- Handlers ----------

    def _on_browse_output_path(self) -> None:
        start = self._output_path.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select output folder", start)
        if chosen:
            chosen = os.path.normpath(chosen)
            self._output_path.setText(chosen)
            self._vm.set_output_dir(chosen)

    def _on_download_gradebook(self) -> None:
        self._vm.download_gradebook()

    def _on_download_consent(self) -> None:
        self._vm.download_consent()

    def _on_download_gradescope(self) -> None:
        self._vm.download_gradescope_submissions()

    def _on_course_changed(self, course_id: str) -> None:
        """Single writer of the view model's course id, for both input modes.

        A picker change is a commit, so dependents load at once. Manual text
        is only stored here; it commits on Enter or focus-out so partial IDs
        never hit the Canvas API while the user is still typing.

        Leaving a course with some of its downloads done asks first, so a
        half-finished dataset is not abandoned by accident. Declining puts
        the picker back, which re-enters here; the flag makes that re-entry
        a no-op so the view model never sees the change.
        """
        if self._reverting_course:
            return
        state = self._vm.get_state()
        if self._should_confirm_course_switch(state, course_id) and not (
            self._confirm_course_switch(state)
        ):
            self._reverting_course = True
            try:
                self._select_course_in_picker(state.selected_course_id)
            finally:
                self._reverting_course = False
            return
        self._vm.set_course_id(course_id)
        if self._course_input.mode() is InputMode.PICKER:
            self._load_course_dependents(course_id)

    def _should_confirm_course_switch(self, state: DownloadUiState, course_id: str) -> bool:
        return (
            not self._rendering
            and self._course_input.mode() is InputMode.PICKER
            and bool(state.selected_course_id)
            and course_id != state.selected_course_id
            and state.canvas_downloads_partial
        )

    def _confirm_course_switch(self, state: DownloadUiState) -> bool:
        """Ask whether to leave a course whose downloads are only partly done."""
        done = [n for n in _CANVAS_DOWNLOAD_ORDER if n in state.completed]
        pending = [n for n in _CANVAS_DOWNLOAD_ORDER if n not in state.completed]
        course = state.selected_course
        course_text = state.selected_course_id
        if course is not None:
            course_text = course.course_code or course.name
        answer = QMessageBox.question(
            self,
            "Switch Canvas course?",
            f"{course_text} still has downloads pending.\n\n"
            f"Done: {', '.join(done)}\n"
            f"Not yet: {', '.join(pending)}\n\n"
            "Switch course anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _select_course_in_picker(self, course_id: str) -> None:
        combo = self._course_picker.combo
        index = combo.findData(course_id)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _on_course_mode_changed(self, mode: InputMode) -> None:
        # Text already sitting in the manual field counts as committed.
        if mode is InputMode.MANUAL:
            self._load_course_dependents(self._course_input.value())

    def _on_course_id_committed(self) -> None:
        if self._course_input.mode() is InputMode.MANUAL:
            self._load_course_dependents(self._course_input.value())

    def _load_course_dependents(self, course_id: str) -> None:
        if not course_id:
            return
        state = self._vm.get_state()
        already_loaded = state.selected_course_id == course_id and bool(
            state.quizzes or state.assignments
        )
        if already_loaded:
            return
        self._vm.load_quizzes(course_id)
        self._vm.load_assignments(course_id)

    def _on_reload_quizzes(self) -> None:
        course_id = self._vm.get_state().selected_course_id
        if course_id:
            self._vm.load_quizzes(course_id)

    def _on_reload_assignments(self) -> None:
        course_id = self._vm.get_state().selected_course_id
        if course_id:
            self._vm.load_assignments(course_id)

    def _on_download_all(self) -> None:
        self._vm.download_all()

    # ---------- View model rendering ----------

    def render(self, state: DownloadUiState) -> None:
        """Paint ``state``; nested changes are folded into one follow-up pass.

        Filling a picker can select an item, which writes to the view model
        and emits ``state_changed`` while this render is still running. A
        nested render would paint the newer state, only for the outer pass
        to resume with its stale copy and undo it (for example, clearing a
        just-loaded assignment list). So a render in progress records the
        request instead, and the outer pass repeats with the latest state
        until nothing changes.
        """
        if self._rendering:
            self._render_pending = True
            return
        self._rendering = True
        try:
            self._render(state)
            while self._render_pending:
                self._render_pending = False
                self._render(self._vm.get_state())
        finally:
            self._rendering = False

    def _render(self, state: DownloadUiState) -> None:
        self._busy_bar.setVisible(state.is_busy)

        if self._output_path.text() != state.output_dir:
            self._output_path.blockSignals(True)
            try:
                self._output_path.setText(state.output_dir)
            finally:
                self._output_path.blockSignals(False)

        self._roster_warning.setVisible(not state.roster_configured)
        self._term_input.set_picker_available(
            state.roster_configured,
            "The term list needs the myASU roster client. Set ROSTER_AUTH_METHOD in .env.",
        )
        self._section_input.set_picker_available(
            state.roster_configured,
            "Section search needs the myASU roster client. Set ROSTER_AUTH_METHOD in .env.",
        )

        token_missing = not state.canvas_token_available
        self._canvas_warning.setVisible(token_missing)
        self._canvas_recheck_btn.setVisible(token_missing)
        self._course_input.set_picker_available(
            not token_missing,
            "The course list needs CANVAS_TOKEN. Enter the course ID directly, "
            "or set the token and press Recheck.",
        )
        self._quiz_input.set_picker_available(
            not token_missing,
            "The quiz list needs CANVAS_TOKEN. Enter the quiz ID directly, "
            "or set the token and press Recheck.",
        )
        self._assignment_input.set_picker_available(
            not token_missing,
            "The assignment list needs CANVAS_TOKEN. Enter assignment IDs directly, "
            "or set the token and press Recheck.",
        )
        credentials_missing = not state.canvas_credentials_available
        self._gradescope_credentials_warning.setVisible(credentials_missing)
        self._gradescope_credentials_recheck_btn.setVisible(credentials_missing)
        self._status_pill.set_status(state.status)
        self._message_label.setText(state.message)

        section_warning = state.section_warning
        self._section_mismatch_warning.setText(section_warning or "")
        self._section_mismatch_warning.setVisible(section_warning is not None)

        for name, buttons in self._download_buttons.items():
            for button in buttons:
                label = self._button_labels[button]
                button.setText(f"{label} {DONE_MARK}" if name in state.completed else label)

        busy = state.is_busy
        self._term_input.set_busy(busy)
        self._section_input.set_busy(busy)
        self._course_input.set_busy(busy)
        self._quiz_input.set_busy(busy)
        self._assignment_input.set_busy(busy)
        self._download_roster_btn.setEnabled(not busy and state.can_download_roster)
        self._download_gradebook_btn.setEnabled(not busy and state.can_download_gradebook)
        self._download_gradescope_btn.setEnabled(not busy and state.can_download_submissions)
        self._download_consent_btn.setEnabled(not busy and state.can_download_consent)
        self._download_rubric_btn.setEnabled(not busy and state.can_download_rubric)
        self._download_all_rubric_btn.setEnabled(
            not busy and state.can_download_all_rubric_assessments
        )
        self._download_all_btn.setEnabled(not busy and state.can_download_all)

        if self._term_picker.combo.count() != len(state.terms):
            self._term_picker.set_items(
                [(t.code, f"{t.code}  {t.name}") for t in state.terms],
                select=state.selected_term,
            )

        if self._section_picker.combo.count() != len(state.sections):
            self._section_picker.set_items(
                [(s.class_number, s.display_label) for s in state.sections],
                select=state.class_number,
            )

        if self._course_picker.combo.count() != len(state.courses):
            self._course_picker.set_items(
                [(str(c.id), _course_label(c)) for c in state.courses],
                select=state.selected_course_id,
            )

        if self._quiz_picker.combo.count() != len(state.quizzes):
            self._quiz_picker.set_items(
                [(str(q.id), _quiz_label(q)) for q in state.quizzes],
                select=state.selected_consent_quiz_id or _likely_consent_quiz(state.quizzes),
            )

        if self._assignment_picker.count() != len(state.assignments):
            self._assignment_picker.set_items(
                [(str(a.id), _assignment_label(a)) for a in state.assignments],
                select=state.assignment_ids,
            )
            for box, assignment in zip(
                self._assignment_picker.boxes(), state.assignments, strict=True
            ):
                if not assignment.has_rubric:
                    box.setToolTip(_NO_RUBRIC_TIP)

        if state.last_saved_path:
            self._last_saved_label.setText(state.last_saved_path)
            self._last_saved_label.show()
        else:
            self._last_saved_label.clear()
            self._last_saved_label.hide()

    def _handle_event(self, event: object) -> None:
        if isinstance(event, ShowError):
            QMessageBox.critical(self, "Roster Download", event.message)
        elif isinstance(event, ShowInfo):
            QMessageBox.information(self, "Roster Download", event.message)
