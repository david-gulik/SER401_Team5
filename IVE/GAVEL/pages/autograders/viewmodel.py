from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass(frozen=True)
class AutogradersUiState:
    """Everything the Autograders tab needs to paint itself."""


class AutogradersViewModel(QObject):
    state_changed = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self._state = AutogradersUiState()

    def get_state(self) -> AutogradersUiState:
        return self._state