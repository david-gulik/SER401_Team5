from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
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
from GAVEL.ui_components.layout import set_spacing
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

        self.add_section(self._build_output_path_card())
        self.add_section(self._build_myasu_card())
        self.add_section(self._build_canvas_card())
        self.add_section(self._build_status_card())
        self.add_section(self._build_download_all())
        self.add_stretch()

        self.render(self._vm.get_state())

    # ---------- Widget construction ----------

    def _build_widgets(self) -> None:
        # Output path
        self._output_path = QLineEdit()
        self._output_path.setPlaceholderText("Enter custom output path")
        self._reset_path_btn = QPushButton("Reset to Default")
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
        self._download_roster_btn.setProperty("role", "primary")

        # Canvas - warning banner
        self._canvas_warning = QLabel(
            "Warning: CANVAS_TOKEN not found in .env file. Please set it to use Canvas features."
        )
        self._canvas_warning.setProperty("role", "warning")
        self._canvas_warning.setWordWrap(True)
        self._canvas_warning.hide()

        # Canvas - course selection
        self._course_combo = QComboBox()
        self._course_combo.setEnabled(False)
        self._course_id_override = QLineEdit()
        self._course_id_override.setPlaceholderText("Enter course ID directly")

        # Canvas - gradebook
        self._download_gradebook_btn = QPushButton("Download Gradebook")
        self._download_gradebook_btn.setProperty("role", "primary")

        # Canvas - consent form
        self._consent_quiz_combo = QComboBox()
        self._consent_quiz_combo.setEnabled(False)
        self._download_consent_btn = QPushButton("Download Consent Form")
        self._download_consent_btn.setProperty("role", "primary")

        # Gradescope submissions
        self._download_gradescope_btn = QPushButton("Download Submissions")
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
        self._consent_quiz_combo.currentIndexChanged.connect(self._vm.set_selected_consent_quiz)

        # Stubs: controls added for the new scaffold. Functionality lands later.
        self._reset_path_btn.clicked.connect(self._on_reset_path)
        self._download_gradebook_btn.clicked.connect(self._on_download_gradebook)
        self._download_consent_btn.clicked.connect(self._on_download_consent)
        self._download_gradescope_btn.clicked.connect(self._on_download_gradescope)
        self._download_all_btn.clicked.connect(self._on_download_all)

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
        card.add_row(self._canvas_warning)

        # Course Selection
        course_panel = SubPanel(self._theme, "Course Selection")
        course_panel.add_widget(self._option_label("Option 1: Select from Course List"))

        course_host = QWidget()
        course_form = QFormLayout(course_host)
        course_form.setContentsMargins(0, 0, 0, 0)
        set_spacing(course_form, self._theme, 8)
        course_form.addRow("Course", self._course_combo)
        course_panel.add_widget(course_host)

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

        # Gradescope Submissions
        gradescope_panel = SubPanel(self._theme, "Gradescope Submissions")
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

    # ---------- Stub handlers ----------

    def _on_reset_path(self) -> None:
        pass

    def _on_download_gradebook(self) -> None:
        pass

    def _on_download_consent(self) -> None:
        pass

    def _on_download_gradescope(self) -> None:
        pass

    def _on_download_all(self) -> None:
        pass

    def _on_term_changed(self, text: str) -> None:
        code = text.split("  ")[0].strip() if text else ""
        self._vm.set_term(code)

    def _on_course_changed(self, index: int) -> None:
        course_id = self._course_combo.itemData(index) or ""
        self._vm.set_course_id(course_id)

    # ---------- View model rendering ----------

    def render(self, state: DownloadUiState) -> None:
        self._status_pill.set_status(state.status)
        self._message_label.setText(state.message)

        busy = state.is_busy
        self._load_terms_btn.setEnabled(not busy)
        self._find_sections_btn.setEnabled(not busy)
        self._download_roster_btn.setEnabled(not busy and state.can_download_roster)
        self._download_gradebook_btn.setEnabled(not busy and state.can_download_gradebook)
        self._download_gradescope_btn.setEnabled(not busy and state.can_download_submissions)
        self._download_consent_btn.setEnabled(not busy and state.can_download_consent)
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
