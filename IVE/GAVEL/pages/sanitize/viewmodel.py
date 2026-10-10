from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass(frozen=True)
class SanitizeUiState:
    """Everything the Sanitize tab needs to paint itself."""


class SanitizeViewModel(QObject):
    state_changed = pyqtSignal(object)  # SanitizeUiState

    def __init__(self) -> None:
        super().__init__()
        self._state = SanitizeUiState()

    def get_state(self) -> SanitizeUiState:
        return self._state
