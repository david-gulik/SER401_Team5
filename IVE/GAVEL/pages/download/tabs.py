from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.download.viewmodel import (
    DownloadUiState,
    DownloadViewModel,
    ShowError,
    ShowInfo,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_h_margins, set_spacing
from GAVEL.ui_components.section_card import SectionCard
from GAVEL.ui_components.status_pill import StatusPill
from GAVEL.ui_components.sub_panel import SubPanel


class DownloadTab(ScrollableTab):
    def __init__(self, theme: ThemeContext, vm: DownloadViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm

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

        # myASU - Step 1: Select Term
        self._term_combo = QComboBox()
        self._load_terms_btn = QPushButton("Load Terms")
        self._term_code_override = QLineEdit()
        self._term_code_override.setPlaceholderText("e.g. 2267 (Format: 2[YY][T])")
        self._term_code_hint = QLabel(
            "Format: 2[YY][T] where T = 1:Spring, 4:Summer, 7:Fall, 9:Winter"
        )
        self._term_code_hint.setProperty("role", "text_muted")
        self._term_code_hint.setWordWrap(True)

        # myASU - Step 2: Identify Class
        self._subject = QLineEdit()
        self._subject.setPlaceholderText("e.g. SER")
        self._catalog_number = QLineEdit()
        self._catalog_number.setPlaceholderText("e.g. 401")
        self._find_sections_btn = QPushButton("Find Sections")
        self._section_combo = QComboBox()
        self._section_combo.setEnabled(False)
        self._class_number = QLineEdit()
        self._class_number.setPlaceholderText("Enter section number directly")

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

        # Canvas - course selection
        self._load_courses_btn = QPushButton("Reload Courses")
        self._course_combo = QComboBox()
        self._course_combo.setEnabled(False)
        self._course_id_override = QLineEdit()
        self._course_id_override.setPlaceholderText("Enter course ID directly")

        # Canvas - gradebook
        self._download_gradebook_btn = QPushButton("Download Gradebook")
        self._download_gradebook_btn.setToolTip("Requires a valid course to be selected above.")
        self._download_gradebook_btn.setProperty("role", "primary")

        # Canvas - consent form
        self._consent_quiz_combo = QComboBox()
        self._consent_quiz_combo.setEnabled(False)
        self._download_consent_btn = QPushButton("Download Consent Form")
        self._download_consent_btn.setToolTip(
            "Requires a valid course and consent quiz to be selected above."
        )
        self._download_consent_btn.setProperty("role", "primary")

        # Canvas - Rubric Assessment
        self._assignment_combo = QComboBox()
        self._assignment_combo.setEnabled(False)
        self._download_rubric_btn = QPushButton("Download Rubric Assessment")
        self._download_rubric_btn.setProperty("role", "primary")
        self._download_rubric_btn.setToolTip(
            "Requires a valid course and assignment to be selected above."
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

    def _connect_signals(self) -> None:
        # Wired to existing view model behavior
        self._load_terms_btn.clicked.connect(self._vm.load_terms)
        self._term_combo.currentTextChanged.connect(self._on_term_changed)
        self._term_code_override.textChanged.connect(self._vm.set_term)
        self._subject.textChanged.connect(self._vm.set_subject)
        self._catalog_number.textChanged.connect(self._vm.set_catalog_number)
        self._find_sections_btn.clicked.connect(self._vm.find_sections)
        self._section_combo.currentIndexChanged.connect(self._vm.set_selected_section)
        self._class_number.textChanged.connect(self._vm.set_class_number)
        self._download_roster_btn.clicked.connect(self._vm.download_roster)

        self._course_combo.currentIndexChanged.connect(self._on_course_changed)
        self._course_id_override.textChanged.connect(self._vm.set_course_id)
        self._consent_quiz_combo.currentIndexChanged.connect(self._on_consent_quiz_changed)
        self._assignment_combo.currentIndexChanged.connect(self._on_assignment_changed)
        self._download_rubric_btn.clicked.connect(self._vm.download_rubric_assessment)

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
        self._load_courses_btn.clicked.connect(self._vm.load_courses)
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

        # Step 1: Select Term
        step1 = SubPanel(self._theme, "Step 1: Select Term")
        step1.add_widget(self._option_label("Option A: Select from Term List"))

        host_a = QWidget()
        form_a = QFormLayout(host_a)
        form_a.setContentsMargins(0, 0, 0, 0)
        set_spacing(form_a, self._theme, 8)
        form_a.addRow("Term", self._term_combo)
        form_a.addRow("", self._load_terms_btn)
        step1.add_widget(host_a)

        step1.add_widget(self._or_divider())

        step1.add_widget(self._option_label("Option B: Enter Term Code Directly"))
        host_b = QWidget()
        form_b = QFormLayout(host_b)
        form_b.setContentsMargins(0, 0, 0, 0)
        set_spacing(form_b, self._theme, 8)
        form_b.addRow("Term Code", self._term_code_override)
        step1.add_widget(host_b)
        step1.add_widget(self._term_code_hint)

        card.add_row(step1)

        # Step 2: Identify Class
        step2 = SubPanel(self._theme, "Step 2: Identify Class")
        step2.add_widget(self._option_label("Option A: Search by Subject and Catalog Number"))

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        set_spacing(grid, self._theme, 8)
        grid.addWidget(QLabel("Subject"), 0, 0)
        grid.addWidget(QLabel("Catalog #"), 0, 1)
        grid.addWidget(self._subject, 1, 0)
        grid.addWidget(self._catalog_number, 1, 1)
        step2.add_widget(grid_host)

        step2.add_widget(self._find_sections_btn)

        section_host = QWidget()
        section_form = QFormLayout(section_host)
        section_form.setContentsMargins(0, 0, 0, 0)
        set_spacing(section_form, self._theme, 8)
        section_form.addRow("Section", self._section_combo)
        step2.add_widget(section_host)

        step2.add_widget(self._or_divider())

        step2.add_widget(self._option_label("Option B: Enter Section Number Directly"))
        direct_host = QWidget()
        direct_form = QFormLayout(direct_host)
        direct_form.setContentsMargins(0, 0, 0, 0)
        set_spacing(direct_form, self._theme, 8)
        direct_form.addRow("Section Number", self._class_number)
        step2.add_widget(direct_host)

        card.add_row(step2)

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
        course_panel = SubPanel(self._theme, "Course Selection")
        course_panel.add_widget(self._option_label("Option 1: Select from Course List"))

        course_host = QWidget()
        course_form = QFormLayout(course_host)
        course_form.setContentsMargins(0, 0, 0, 0)
        set_spacing(course_form, self._theme, 8)
        course_form.addRow("Course", self._course_combo)
        course_panel.add_widget(course_host)
        course_panel.add_widget(self._load_courses_btn)

        course_panel.add_widget(self._or_divider())

        course_panel.add_widget(self._option_label("Option 2: Enter Course ID Directly"))
        course_id_host = QWidget()
        course_id_form = QFormLayout(course_id_host)
        course_id_form.setContentsMargins(0, 0, 0, 0)
        set_spacing(course_id_form, self._theme, 8)
        course_id_form.addRow("Course ID", self._course_id_override)
        course_panel.add_widget(course_id_host)

        card.add_row(course_panel)

        # Canvas Gradebook
        gradebook_panel = SubPanel(self._theme, "Canvas Gradebook")
        gradebook_panel.add_widget(self._download_gradebook_btn)
        card.add_row(gradebook_panel)

        # Canvas Consent Form
        consent_panel = SubPanel(self._theme, "Canvas Consent Form")
        consent_host = QWidget()
        consent_form = QFormLayout(consent_host)
        consent_form.setContentsMargins(0, 0, 0, 0)
        set_spacing(consent_form, self._theme, 8)
        consent_form.addRow("Consent Quiz", self._consent_quiz_combo)
        consent_panel.add_widget(consent_host)
        consent_panel.add_widget(self._download_consent_btn)
        card.add_row(consent_panel)

        # Rubric Assessment
        rubric_panel = SubPanel(self._theme, "Rubric Assessment")
        rubric_host = QWidget()
        rubric_form = QFormLayout(rubric_host)
        rubric_form.setContentsMargins(0, 0, 0, 0)
        set_spacing(rubric_form, self._theme, 8)
        rubric_form.addRow("Assignment", self._assignment_combo)
        rubric_panel.add_widget(rubric_host)
        rubric_panel.add_widget(self._download_rubric_btn)
        card.add_row(rubric_panel)

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

    # ---------- Small layout helpers ----------

    def _option_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "text_muted")
        label.setWordWrap(True)
        return label

    def _or_divider(self) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(layout, self._theme, 8)

        left = QFrame()
        left.setFrameShape(QFrame.Shape.HLine)
        left.setFrameShadow(QFrame.Shadow.Sunken)

        right = QFrame()
        right.setFrameShape(QFrame.Shape.HLine)
        right.setFrameShadow(QFrame.Shadow.Sunken)

        label = QLabel("OR")
        label.setProperty("role", "text_muted")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(left, 1)
        layout.addWidget(label)
        layout.addWidget(right, 1)
        return host

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

    def _on_term_changed(self, text: str) -> None:
        code = text.split("  ")[0].strip() if text else ""
        self._vm.set_term(code)

    def _on_course_changed(self, index: int) -> None:
        course_id = self._course_combo.itemData(index) or ""
        self._vm.set_course_id(course_id)
        if course_id:
            self._vm.load_quizzes(course_id)
            self._vm.load_assignments(course_id)

    def _on_consent_quiz_changed(self, index: int) -> None:
        quiz_id = self._consent_quiz_combo.itemData(index) or ""
        self._vm.set_consent_quiz_id(str(quiz_id))

    def _on_assignment_changed(self, index: int) -> None:
        assignment_id = self._assignment_combo.itemData(index) or ""
        self._vm.set_assignment_id(str(assignment_id))

    def _on_download_all(self) -> None:
        self._vm.download_all()

    # ---------- View model rendering ----------

    def render(self, state: DownloadUiState) -> None:
        self._busy_bar.setVisible(state.is_busy)

        if self._output_path.text() != state.output_dir:
            self._output_path.blockSignals(True)
            try:
                self._output_path.setText(state.output_dir)
            finally:
                self._output_path.blockSignals(False)

        token_missing = not state.canvas_token_available
        self._canvas_warning.setVisible(token_missing)
        self._canvas_recheck_btn.setVisible(token_missing)
        credentials_missing = not state.canvas_credentials_available
        self._gradescope_credentials_warning.setVisible(credentials_missing)
        self._gradescope_credentials_recheck_btn.setVisible(credentials_missing)
        self._status_pill.set_status(state.status)
        self._message_label.setText(state.message)

        busy = state.is_busy
        self._load_terms_btn.setEnabled(not busy)
        self._load_courses_btn.setEnabled(not busy)
        self._find_sections_btn.setEnabled(not busy)
        self._download_roster_btn.setEnabled(not busy and state.can_download_roster)
        self._download_gradebook_btn.setEnabled(not busy and state.can_download_gradebook)
        self._download_gradescope_btn.setEnabled(not busy and state.can_download_submissions)
        self._download_consent_btn.setEnabled(not busy and state.can_download_consent)
        self._download_rubric_btn.setEnabled(not busy and state.can_download_rubric)
        self._download_all_btn.setEnabled(not busy and state.can_download_all)

        if state.terms and self._term_combo.count() != len(state.terms):
            self._term_combo.blockSignals(True)
            try:
                self._term_combo.clear()
                for t in state.terms:
                    self._term_combo.addItem(f"{t.code}  {t.name}", t.code)
                if state.selected_term:
                    for i in range(self._term_combo.count()):
                        if self._term_combo.itemData(i) == state.selected_term:
                            self._term_combo.setCurrentIndex(i)
                            break
            finally:
                self._term_combo.blockSignals(False)

        if state.sections:
            self._section_combo.setEnabled(True)
            if self._section_combo.count() != len(state.sections):
                self._section_combo.blockSignals(True)
                try:
                    self._section_combo.clear()
                    for s in state.sections:
                        self._section_combo.addItem(s.display_label, s.class_number)
                finally:
                    self._section_combo.blockSignals(False)
        else:
            self._section_combo.setEnabled(False)
            if self._section_combo.count():
                self._section_combo.clear()

        if state.courses:
            self._course_combo.setEnabled(True)
            if self._course_combo.count() != len(state.courses):
                self._course_combo.blockSignals(True)
                try:
                    self._course_combo.clear()
                    for c in state.courses:
                        label = f"{c.course_code}  {c.name}" if c.course_code else c.name
                        self._course_combo.addItem(label, str(c.id))
                finally:
                    self._course_combo.blockSignals(False)
                self._on_course_changed(0)
        else:
            self._course_combo.setEnabled(False)
            if self._course_combo.count():
                self._course_combo.clear()

        if state.quizzes:
            self._consent_quiz_combo.setEnabled(True)
            if self._consent_quiz_combo.count() != len(state.quizzes):
                self._consent_quiz_combo.blockSignals(True)
                try:
                    self._consent_quiz_combo.clear()
                    for q in state.quizzes:
                        self._consent_quiz_combo.addItem(q.name, q.id)
                    consent_idx = next(
                        (i for i, q in enumerate(state.quizzes) if "consent" in q.name.lower()),
                        0,
                    )
                    self._consent_quiz_combo.setCurrentIndex(consent_idx)
                finally:
                    self._consent_quiz_combo.blockSignals(False)
                self._on_consent_quiz_changed(self._consent_quiz_combo.currentIndex())
        else:
            self._consent_quiz_combo.setEnabled(False)
            if self._consent_quiz_combo.count():
                self._consent_quiz_combo.clear()

        if state.assignments:
            self._assignment_combo.setEnabled(True)
            if self._assignment_combo.count() != len(state.assignments):
                self._assignment_combo.blockSignals(True)
                try:
                    self._assignment_combo.clear()
                    for a in state.assignments:
                        self._assignment_combo.addItem(a.name, a.id)
                finally:
                    self._assignment_combo.blockSignals(False)
                self._on_assignment_changed(self._assignment_combo.currentIndex())
        else:
            self._assignment_combo.setEnabled(False)
            if self._assignment_combo.count():
                self._assignment_combo.clear()

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
