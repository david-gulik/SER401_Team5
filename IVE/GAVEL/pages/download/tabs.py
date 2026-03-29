from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
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


class DownloadTab(ScrollableTab):
    def __init__(self, theme: ThemeContext, vm: DownloadViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm

        # Widgets
        self._term_combo = QComboBox()
        self._load_terms_btn = QPushButton("Load Terms")
        self._subject = QLineEdit()
        self._subject.setPlaceholderText("e.g. SER")
        self._catalog_number = QLineEdit()
        self._catalog_number.setPlaceholderText("e.g. 401")
        self._find_sections_btn = QPushButton("Find Sections")

        self._section_combo = QComboBox()
        self._section_combo.setEnabled(False)

        self._class_number = QLineEdit()
        self._class_number.setPlaceholderText("Direct class number (optional)")

        self._download_btn = QPushButton("Download Roster")
        self._status_pill = StatusPill(theme)
        self._message_label = QLabel("")
        self._message_label.setWordWrap(True)
        self._last_saved_label = QLabel("")
        self._last_saved_label.setWordWrap(True)
        self._last_saved_label.setProperty("role", "text_muted")
        self._last_saved_label.hide()

        # Signals
        self._load_terms_btn.clicked.connect(self._vm.load_terms)
        self._term_combo.currentTextChanged.connect(self._on_term_changed)
        self._subject.textChanged.connect(self._vm.set_subject)
        self._catalog_number.textChanged.connect(self._vm.set_catalog_number)
        self._find_sections_btn.clicked.connect(self._vm.find_sections)
        self._section_combo.currentIndexChanged.connect(self._vm.set_selected_section)
        self._class_number.textChanged.connect(self._vm.set_class_number)
        self._download_btn.clicked.connect(self._vm.download_roster)

        self._vm.state_changed.connect(self.render)
        self._vm.event_raised.connect(self._handle_event)

        # Layout
        self.add_section(self._build_search_card())
        self.add_section(self._build_download_card())
        self.add_stretch()

        self.render(self._vm.get_state())

    def _build_search_card(self) -> QWidget:
        card = SectionCard(self._theme, "Section Lookup")

        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)
        set_spacing(form, self._theme, 8)

        term_row = QWidget()
        term_layout = QFormLayout(term_row)
        term_layout.setContentsMargins(0, 0, 0, 0)
        term_layout.addRow(self._term_combo)
        term_layout.addRow(self._load_terms_btn)

        form.addRow("Term", term_row)
        form.addRow("Subject", self._subject)
        form.addRow("Catalog #", self._catalog_number)
        form.addRow("", self._find_sections_btn)
        form.addRow("Sections", self._section_combo)

        card.add_row(host)
        return card

    def _build_download_card(self) -> QWidget:
        card = SectionCard(self._theme, "Roster Download")

        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)
        set_spacing(form, self._theme, 8)

        form.addRow("Class # (override)", self._class_number)
        form.addRow("", self._download_btn)
        form.addRow("Status", self._status_pill)
        form.addRow("Message", self._message_label)
        form.addRow("Last Saved", self._last_saved_label)

        card.add_row(host)
        return card

    def _on_term_changed(self, text: str) -> None:
        code = text.split("  ")[0].strip() if text else ""
        self._vm.set_term(code)

    def render(self, state: DownloadUiState) -> None:
        self._status_pill.set_status(state.status)
        self._message_label.setText(state.message)

        busy = state.is_busy
        self._load_terms_btn.setEnabled(not busy)
        self._find_sections_btn.setEnabled(not busy)
        self._download_btn.setEnabled(not busy)

        # Populate terms combo if changed
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

        # Populate sections combo if changed
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
