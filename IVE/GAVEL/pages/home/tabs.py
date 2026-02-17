from __future__ import annotations

from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.home.viewmodel import (
    HomeShowError,
    HomeShowInfo,
    HomeUiState,
    HomeViewModel,
)
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing
from GAVEL.ui_components.section_card import SectionCard
from GAVEL.ui_components.status_pill import StatusPill


class OverviewTab(ScrollableTab):
    def __init__(self, theme: ThemeContext, vm: HomeViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm

        self._env_label = QLabel("")
        self._version_label = QLabel("")
        self._message_label = QLabel("")
        self._message_label.setWordWrap(True)
        self._overall_status = StatusPill(theme)

        self._vm.state_changed.connect(self._apply_state)
        self._vm.event_raised.connect(self._handle_event)

        self.add_section(self._build_status_card())
        self.add_section(self._build_quick_actions_card())
        self.add_stretch()

        self._apply_state(self._vm.get_state())

    def _build_status_card(self) -> QWidget:
        card = SectionCard(self._theme, "Status")
        card.add_row(self._build_row("Environment:", self._env_label))
        card.add_row(self._build_row("Version:", self._version_label))
        card.add_row(self._overall_status)
        card.add_row(self._build_row("Message:", self._message_label))
        return card

    def _build_quick_actions_card(self) -> QWidget:
        card = SectionCard(self._theme, "Quick Actions")

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(row_layout, self._theme, 8)

        run_btn = QPushButton("Run")
        run_btn.clicked.connect(self._vm.run)

        validate_btn = QPushButton("Validate")
        validate_btn.clicked.connect(self._vm.validate)

        row_layout.addWidget(run_btn)
        row_layout.addWidget(validate_btn)
        row_layout.addStretch(1)

        card.add_row(row)
        return card

    def _apply_state(self, state: HomeUiState) -> None:
        self._env_label.setText(state.environment)
        self._version_label.setText(state.version)
        self._overall_status.set_status(state.status)
        self._message_label.setText(state.message)

    def _handle_event(self, event: object) -> None:
        targets = {"overview", "global"}
        if isinstance(event, HomeShowError) and event.target in targets:
            QMessageBox.critical(self, "Home", event.message)
        elif isinstance(event, HomeShowInfo) and event.target in targets:
            QMessageBox.information(self, "Home", event.message)

    def _build_row(self, title: str, value_widget: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(layout, self._theme, 8)
        layout.addWidget(QLabel(title))
        layout.addWidget(value_widget, 1)
        return row


class DataEntryTab(ScrollableTab):
    def __init__(self, theme: ThemeContext, vm: HomeViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm

        self._name = QLineEdit()
        self._tag = QLineEdit()

        self._vm.event_raised.connect(self._handle_event)

        self.add_section(self._build_inputs_card())
        self.add_stretch()

    def _build_inputs_card(self) -> QWidget:
        card = SectionCard(self._theme, "Inputs")

        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)
        set_spacing(form, self._theme, 8)

        form.addRow("Name:", self._name)
        form.addRow("Tag:", self._tag)

        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self._on_submit)

        form.addRow("", submit_btn)

        card.add_row(host)
        return card

    def _on_submit(self) -> None:
        self._vm.submit_entry(self._name.text(), self._tag.text())

    def _handle_event(self, event: object) -> None:
        targets = {"data_entry", "global"}
        if isinstance(event, HomeShowError) and event.target in targets:
            QMessageBox.critical(self, "Home Data Entry", event.message)
        elif isinstance(event, HomeShowInfo) and event.target in targets:
            QMessageBox.information(self, "Home Data Entry", event.message)
