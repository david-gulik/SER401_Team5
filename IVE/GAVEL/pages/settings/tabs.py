from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QFormLayout, QLabel, QWidget

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.settings.viewmodel import SettingsUiState, SettingsViewModel
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing
from GAVEL.ui_components.section_card import SectionCard


class PreferencesTab(ScrollableTab):
    def __init__(self, theme: ThemeContext, vm: SettingsViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm

        self._chk_feature_x = QCheckBox()
        self._chk_logging = QCheckBox()

        self._chk_feature_x.toggled.connect(self._vm.set_enable_feature_x)
        self._chk_logging.toggled.connect(self._vm.set_enable_logging)

        self._vm.state_changed.connect(self._apply_state)

        self.add_section(self._build_preferences_card())
        self.add_stretch()

        self._apply_state(self._vm.get_state())

    def _build_preferences_card(self) -> QWidget:
        card = SectionCard(self._theme, "Preferences")

        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)
        set_spacing(form, self._theme, 8)

        form.addRow("Enable feature X:", self._chk_feature_x)
        form.addRow("Enable logging:", self._chk_logging)

        card.add_row(host)
        return card

    def _apply_state(self, state: SettingsUiState) -> None:
        self._chk_feature_x.blockSignals(True)
        self._chk_logging.blockSignals(True)
        try:
            self._chk_feature_x.setChecked(state.enable_feature_x)
            self._chk_logging.setChecked(state.enable_logging)
        finally:
            self._chk_feature_x.blockSignals(False)
            self._chk_logging.blockSignals(False)


class AboutTab(ScrollableTab):
    def __init__(self, theme: ThemeContext, vm: SettingsViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm

        self._env_label = QLabel("")
        self._version_label = QLabel("")

        self._vm.state_changed.connect(self._apply_state)

        self.add_section(self._build_about_card())
        self.add_stretch()

        self._apply_state(self._vm.get_state())

    def _build_about_card(self) -> QWidget:
        card = SectionCard(self._theme, "About")
        card.add_row(QLabel("Application: Modular PyQt Shell"))
        card.add_row(self._wrap_row("Environment:", self._env_label))
        card.add_row(self._wrap_row("Version:", self._version_label))
        return card

    def _wrap_row(self, title: str, value_label: QLabel) -> QWidget:
        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)
        set_spacing(form, self._theme, 4)
        form.addRow(title, value_label)
        return host

    def _apply_state(self, state: SettingsUiState) -> None:
        self._env_label.setText(state.environment)
        self._version_label.setText(state.version)
