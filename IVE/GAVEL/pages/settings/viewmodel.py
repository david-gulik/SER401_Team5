from __future__ import annotations

from dataclasses import dataclass, replace

from PyQt6.QtCore import QObject, pyqtSignal

from GAVEL.services.config_service import ConfigService
from GAVEL.services.logger import AppLogger


@dataclass(frozen=True)
class SettingsUiState:
    enable_feature_x: bool
    enable_logging: bool
    environment: str
    version: str


class SettingsViewModel(QObject):
    state_changed = pyqtSignal(object)  # emits SettingsUiState

    def __init__(self, config: ConfigService, logger: AppLogger) -> None:
        super().__init__()
        self._config = config
        self._logger = logger

        cfg = self._config.get()
        self._state = SettingsUiState(
            enable_feature_x=False,
            enable_logging=True,
            environment=cfg.environment,
            version=cfg.version,
        )

    def get_state(self) -> SettingsUiState:
        return self._state

    def set_enable_feature_x(self, value: bool) -> None:
        if value == self._state.enable_feature_x:
            return
        self._state = replace(self._state, enable_feature_x=value)
        self._logger.info(f"Preference changed: enable_feature_x={value}")
        self.state_changed.emit(self._state)

    def set_enable_logging(self, value: bool) -> None:
        if value == self._state.enable_logging:
            return
        self._state = replace(self._state, enable_logging=value)
        self._logger.info(f"Preference changed: enable_logging={value}")
        self.state_changed.emit(self._state)
