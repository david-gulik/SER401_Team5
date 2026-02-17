from __future__ import annotations

from PyQt6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.canvas_course.viewmodel import (
    CanvasCourseUiState,
    CanvasCourseViewModel,
    ShowError,
    ShowInfo,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing
from GAVEL.ui_components.section_card import SectionCard
from GAVEL.ui_components.status_pill import StatusPill


class CanvasCourseTab(ScrollableTab):
    def __init__(self, theme: ThemeContext, vm: CanvasCourseViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm

        self._course_id = QLineEdit()
        self._download_btn = QPushButton("Download")
        self._status_pill = StatusPill(theme)
        self._message_label = QLabel("")
        self._message_label.setWordWrap(True)
        self._last_saved_label = QLabel("")
        self._last_saved_label.setWordWrap(True)
        self._last_saved_label.setProperty("role", "text_muted")
        self._last_saved_label.hide()

        self._course_id.textChanged.connect(self._vm.set_course_id)
        self._download_btn.clicked.connect(self._vm.download_course)
        self._vm.state_changed.connect(self.render)
        self._vm.event_raised.connect(self._handle_event)

        self.add_section(self._build_form_card())
        self.add_stretch()

        self.render(self._vm.get_state())

    def _build_form_card(self) -> QWidget:
        card = SectionCard(self._theme, "Canvas Course Download")

        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)
        set_spacing(form, self._theme, 8)

        form.addRow("Course ID", self._course_id)
        form.addRow("", self._download_btn)
        form.addRow("Status", self._status_pill)
        form.addRow("Message", self._message_label)
        form.addRow("Last Saved", self._last_saved_label)

        card.add_row(host)
        return card

    def render(self, state: CanvasCourseUiState) -> None:
        self._status_pill.set_status(state.status)
        self._message_label.setText(state.message)

        self._download_btn.setEnabled(not state.is_busy)

        if self._course_id.text() != state.course_id:
            self._course_id.blockSignals(True)
            try:
                self._course_id.setText(state.course_id)
            finally:
                self._course_id.blockSignals(False)

        if state.last_saved_path:
            self._last_saved_label.setText(state.last_saved_path)
            self._last_saved_label.show()
        else:
            self._last_saved_label.clear()
            self._last_saved_label.hide()

    def _handle_event(self, event: object) -> None:
        if isinstance(event, ShowError):
            QMessageBox.critical(self, "Canvas Course", event.message)
        elif isinstance(event, ShowInfo):
            QMessageBox.information(self, "Canvas Course", event.message)
