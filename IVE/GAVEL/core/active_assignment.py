"""The assignment one page hands to another, with a student when there is one to show."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass(frozen=True)
class AssignmentPick:
    """One module of a workspace course and, optionally, one anonymized submission in it."""

    course: str  # the course folder name
    module_number: int
    submission: str | None = None


class ActiveAssignment(QObject):
    """The assignment the Verification pages look at together.

    Stability Check sets it when the user asks to see a submission in Inspect
    Grades. A page reads ``pick`` when it is built and connects to ``changed``
    for later picks; the main window follows ``page_requested``. Unlike the
    active course, the pick is not remembered between launches.
    """

    changed = pyqtSignal(object)  # AssignmentPick | None
    page_requested = pyqtSignal(str)  # the page_id to show

    def __init__(self) -> None:
        super().__init__()
        self._pick: AssignmentPick | None = None

    @property
    def pick(self) -> AssignmentPick | None:
        return self._pick

    def select(self, pick: AssignmentPick | None) -> None:
        if pick == self._pick:
            return
        self._pick = pick
        self.changed.emit(pick)

    def hand_off(self, pick: AssignmentPick, page_id: str) -> None:
        """Make ``pick`` current and ask for ``page_id`` to be shown."""
        self.select(pick)
        self.page_requested.emit(page_id)
