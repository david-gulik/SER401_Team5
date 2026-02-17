from __future__ import annotations

from dataclasses import dataclass, replace

from PyQt6.QtCore import QObject, pyqtSignal

from GAVEL.core.status import Status
from GAVEL.services.config_service import ConfigService
from GAVEL.services.logger import AppLogger


@dataclass(frozen=True)
class HomeUiState:
    environment: str
    version: str
    status: Status
    message: str


@dataclass(frozen=True)
class HomeShowInfo:
    message: str
    target: str = "global"


@dataclass(frozen=True)
class HomeShowError:
    message: str
    target: str = "global"


class HomeViewModel(QObject):
    state_changed = pyqtSignal(object)  # HomeUiState
    event_raised = pyqtSignal(object)  # HomeShowInfo | HomeShowError

    def __init__(self, config: ConfigService, logger: AppLogger) -> None:
        super().__init__()
        self._config = config
        self._logger = logger

        cfg = self._config.get()
        self._state = HomeUiState(
            environment=cfg.environment,
            version=cfg.version,
            status=Status.UNKNOWN,
            message="Idle",
        )

    def get_state(self) -> HomeUiState:
        return self._state

    def run(self) -> None:
        self._logger.info("HomeViewModel.run invoked")
        self._set_status(Status.WARNING, "Run started...")
        self.event_raised.emit(HomeShowInfo("Run command dispatched.", target="overview"))

    def validate(self) -> None:
        self._logger.info("HomeViewModel.validate invoked")
        self._set_status(Status.NOMINAL, "Validation completed successfully.")
        self.event_raised.emit(HomeShowInfo("Validation finished.", target="overview"))

    def submit_entry(self, name: str, tag: str) -> None:
        cleaned_name = name.strip()
        cleaned_tag = tag.strip()
        if not cleaned_name:
            self.event_raised.emit(HomeShowError("Name is required.", target="data_entry"))
            self._set_status(Status.CRITICAL, "Missing name for submission.")
            return
        self._logger.info(f"DataEntry submit: name={cleaned_name}, tag={cleaned_tag}")
        self._set_status(Status.CAUTION, f"Submitted '{cleaned_name}' with tag '{cleaned_tag}'.")
        self.event_raised.emit(HomeShowInfo("Form submitted.", target="data_entry"))

    def _set_status(self, status: Status, message: str) -> None:
        self._state = replace(self._state, status=status, message=message)
        self.state_changed.emit(self._state)
