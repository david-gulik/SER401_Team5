from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from GAVEL.core.base_tab import ScrollableTab
from GAVEL.pages.settings.viewmodel import SettingsUiState, SettingsViewModel
from GAVEL.services.env_service import EnvVarSpec, grouped_schema
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
        card.add_row(QLabel("Application: GAVEL"))
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


@dataclass
class _FieldHandle:
    spec: EnvVarSpec
    apply_value: Callable[[str], None]


class EnvironmentTab(ScrollableTab):
    """Edit the project .env file with typed inputs grouped by purpose."""

    def __init__(self, theme: ThemeContext, vm: SettingsViewModel) -> None:
        super().__init__(theme)
        self._theme = theme
        self._vm = vm
        self._handles: dict[str, _FieldHandle] = {}
        self._status_label = QLabel("")
        self._status_label.setProperty("role", "text_muted")
        self._status_label.setWordWrap(True)
        self._path_label = QLabel("")
        self._path_label.setProperty("role", "text_muted")
        self._path_label.setWordWrap(True)

        self.add_section(self._build_intro_card())
        for group_name, specs in grouped_schema():
            self.add_section(self._build_group_card(group_name, specs))
        self.add_section(self._build_actions_card())
        self.add_stretch()

        self._vm.state_changed.connect(self._apply_state)
        self._vm.env_saved.connect(self._on_saved)
        self._vm.env_save_failed.connect(self._on_save_failed)

        self._apply_state(self._vm.get_state())

    # ------------------------------------------------------------------
    # Card builders
    # ------------------------------------------------------------------

    def _build_intro_card(self) -> QWidget:
        card = SectionCard(self._theme, "Environment file")
        intro = QLabel(
            "Configure values that GAVEL reads from your .env file. Empty fields are "
            "treated as unset and use built-in defaults. Click the eye icon next to a "
            "secret to reveal it."
        )
        intro.setWordWrap(True)
        card.add_row(intro)
        card.add_row(self._path_label)
        return card

    def _build_group_card(self, title: str, specs: Iterable[EnvVarSpec]) -> QWidget:
        card = SectionCard(self._theme, title)
        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)
        set_spacing(form, self._theme, 12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        for spec in specs:
            form.addRow(f"{spec.label}:", self._build_field(spec))
        card.add_row(host)
        return card

    def _build_actions_card(self) -> QWidget:
        card = SectionCard(self._theme, "Actions")

        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        set_spacing(row, self._theme, 8)

        save_btn = QPushButton("Save")
        save_btn.setProperty("role", "primary")
        save_btn.clicked.connect(self._vm.save_env)

        reload_btn = QPushButton("Reload from disk")
        reload_btn.setProperty("role", "secondary")
        reload_btn.clicked.connect(self._vm.reload_env)

        row.addWidget(save_btn)
        row.addWidget(reload_btn)
        row.addStretch(1)

        card.add_row(host)
        card.add_row(self._status_label)
        return card

    # ------------------------------------------------------------------
    # Field builders
    # ------------------------------------------------------------------

    def _build_field(self, spec: EnvVarSpec) -> QWidget:
        if spec.kind == "secret":
            return self._build_secret(spec)
        if spec.kind == "dropdown":
            return self._build_dropdown(spec)
        if spec.kind == "int":
            return self._build_int(spec)
        if spec.kind == "path":
            return self._build_path(spec)
        return self._build_text(spec)

    def _wrap_field(
        self,
        input_row: QWidget,
        spec: EnvVarSpec,
    ) -> QWidget:
        host = QWidget()
        col = QVBoxLayout(host)
        col.setContentsMargins(0, 0, 0, 0)
        set_spacing(col, self._theme, 4)
        col.addWidget(input_row)
        if spec.help:
            help_label = QLabel(spec.help)
            help_label.setProperty("role", "text_muted")
            help_label.setWordWrap(True)
            col.addWidget(help_label)
        return host

    def _build_text(self, spec: EnvVarSpec) -> QWidget:
        line = QLineEdit()
        if spec.placeholder:
            line.setPlaceholderText(spec.placeholder)
        elif spec.default:
            line.setPlaceholderText(spec.default)
        line.textEdited.connect(lambda text, name=spec.name: self._vm.set_env_value(name, text))

        def apply_value(value: str) -> None:
            line.blockSignals(True)
            try:
                line.setText(value)
            finally:
                line.blockSignals(False)

        self._handles[spec.name] = _FieldHandle(spec, apply_value)
        return self._wrap_field(line, spec)

    def _build_int(self, spec: EnvVarSpec) -> QWidget:
        line = QLineEdit()
        line.setValidator(QIntValidator(0, 86_400, line))
        if spec.default:
            line.setPlaceholderText(spec.default)
        line.textEdited.connect(lambda text, name=spec.name: self._vm.set_env_value(name, text))

        def apply_value(value: str) -> None:
            line.blockSignals(True)
            try:
                line.setText(value)
            finally:
                line.blockSignals(False)

        self._handles[spec.name] = _FieldHandle(spec, apply_value)
        return self._wrap_field(line, spec)

    def _build_secret(self, spec: EnvVarSpec) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(layout, self._theme, 4)

        line = QLineEdit()
        line.setEchoMode(QLineEdit.EchoMode.Password)
        if spec.placeholder:
            line.setPlaceholderText(spec.placeholder)
        line.textEdited.connect(lambda text, name=spec.name: self._vm.set_env_value(name, text))

        toggle = QPushButton("Show")
        toggle.setProperty("role", "secondary")
        toggle.setCheckable(True)
        toggle.setToolTip("Show value")
        toggle.setFixedWidth(32)

        def _toggle(checked: bool) -> None:
            line.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
            toggle.setText("Hide" if checked else "Show")
            toggle.setToolTip("Hide value" if checked else "Show value")

        toggle.toggled.connect(_toggle)

        layout.addWidget(line, 1)
        layout.addWidget(toggle, 0)

        def apply_value(value: str) -> None:
            line.blockSignals(True)
            try:
                line.setText(value)
            finally:
                line.blockSignals(False)

        self._handles[spec.name] = _FieldHandle(spec, apply_value)
        return self._wrap_field(row, spec)

    def _build_dropdown(self, spec: EnvVarSpec) -> QWidget:
        combo = QComboBox()
        for opt in spec.options:
            combo.addItem(opt)
        combo.currentTextChanged.connect(
            lambda value, name=spec.name: self._vm.set_env_value(name, value)
        )

        def apply_value(value: str) -> None:
            combo.blockSignals(True)
            try:
                target = value or spec.default
                idx = combo.findText(target)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                elif combo.count() > 0:
                    combo.setCurrentIndex(0)
            finally:
                combo.blockSignals(False)

        self._handles[spec.name] = _FieldHandle(spec, apply_value)
        return self._wrap_field(combo, spec)

    def _build_path(self, spec: EnvVarSpec) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        set_spacing(layout, self._theme, 4)

        line = QLineEdit()
        if spec.placeholder:
            line.setPlaceholderText(spec.placeholder)
        line.textEdited.connect(lambda text, name=spec.name: self._vm.set_env_value(name, text))

        browse = QPushButton("Browse…")
        browse.setProperty("role", "secondary")

        def _pick() -> None:
            start = line.text().strip() or str(Path.home())
            if spec.path_kind == "folder":
                chosen = QFileDialog.getExistingDirectory(self, f"Select {spec.label}", start)
            else:
                chosen, _ = QFileDialog.getOpenFileName(self, f"Select {spec.label}", start)
            if chosen:
                line.setText(chosen)
                self._vm.set_env_value(spec.name, chosen)

        browse.clicked.connect(_pick)

        layout.addWidget(line, 1)
        layout.addWidget(browse, 0)

        def apply_value(value: str) -> None:
            line.blockSignals(True)
            try:
                line.setText(value)
            finally:
                line.blockSignals(False)

        self._handles[spec.name] = _FieldHandle(spec, apply_value)
        return self._wrap_field(row, spec)

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------

    def _apply_state(self, state: SettingsUiState) -> None:
        self._path_label.setText(f"File: {state.env_path}")
        for name, handle in self._handles.items():
            value = state.env_values.get(name, "")
            handle.apply_value(value)

    def _on_saved(self) -> None:
        self._status_label.setText(
            "Saved. Some changes may require restarting GAVEL to fully apply."
        )

    def _on_save_failed(self, message: str) -> None:
        self._status_label.setText(f"Save failed: {message}")
        QMessageBox.warning(self, "Save failed", message)
