from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from PyQt6.QtCore import QObject, pyqtSignal

from GAVEL.services.config_service import ConfigService
from GAVEL.services.env_service import EnvService
from GAVEL.services.logger import AppLogger


@dataclass(frozen=True)
class SettingsUiState:
    enable_feature_x: bool
    enable_logging: bool
    environment: str
    version: str
    env_values: Mapping[str, str]
    env_path: str


class SettingsViewModel(QObject):
    state_changed = pyqtSignal(object)  # emits SettingsUiState
    env_saved = pyqtSignal()
    env_save_failed = pyqtSignal(str)

    def __init__(
        self,
        config: ConfigService,
        env_service: EnvService,
        logger: AppLogger,
    ) -> None:
        super().__init__()
        self._config = config
        self._env = env_service
        self._logger = logger

        cfg = self._config.get()
        self._state = SettingsUiState(
            enable_feature_x=False,
            enable_logging=True,
            environment=cfg.environment,
            version=cfg.version,
            env_values=dict(self._env.read()),
            env_path=str(self._env.path),
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

    def set_env_value(self, name: str, value: str) -> None:
        """Stage an env value change. Does not emit; tab owns its own widgets."""
        current = self._state.env_values.get(name, "")
        if current == value:
            return
        new_values = dict(self._state.env_values)
        new_values[name] = value
        self._state = replace(self._state, env_values=new_values)

    def reload_env(self) -> None:
        """Discard staged edits and re-read .env from disk."""
        self._state = replace(self._state, env_values=dict(self._env.read()))
        self._logger.info("Reloaded environment values from disk")
        self.state_changed.emit(self._state)

    def save_env(self) -> None:
        try:
            self._env.write(self._state.env_values)
            self._config.reload()
            cfg = self._config.get()
            self._state = replace(
                self._state,
                environment=cfg.environment,
                version=cfg.version,
                env_values=dict(self._env.read()),
            )
            self._logger.info(f"Saved environment configuration to {self._env.path}")
            self.env_saved.emit()
            self.state_changed.emit(self._state)
        except OSError as exc:
            self._logger.error(f"Failed to save .env: {exc}")
            self.env_save_failed.emit(str(exc))
