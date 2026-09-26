from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.roster import RosterRequest
from GAVEL.app.ports.roster_client import RosterClient
from GAVEL.app.usecases.roster import download_roster_to_file
from GAVEL.app.workspace.layout import CourseFolder
from GAVEL.app.workspace.recording import guard_not_downloaded, note_course, record


@dataclass(frozen=True)
class DownloadRosterRequest:
    term: str
    class_number: str
    folder: CourseFolder
    overwrite: bool = False


@dataclass(frozen=True)
class DownloadRosterResult:
    saved_path: Path
    message: str


class DownloadRosterUseCase:
    """Saves the myASU roster as ``original/roster.csv`` in the course folder.

    Owns the authenticate/close pair around the fetch so the GUI and CLI do
    not each repeat it.
    """

    def __init__(self, roster_client: RosterClient) -> None:
        self._client = roster_client

    def execute(self, request: DownloadRosterRequest) -> DownloadRosterResult:
        term = request.term.strip()
        class_number = request.class_number.strip()
        if not term:
            raise ValueError("term is required")
        if not class_number:
            raise ValueError("class_number is required")

        target = request.folder.original.roster_csv
        guard_not_downloaded(request.folder, target, request.overwrite)

        self._client.authenticate()
        try:
            download_roster_to_file(
                self._client, RosterRequest(term=term, class_number=class_number), target
            )
        finally:
            self._client.close()

        record(request.folder, "roster", target)
        note_course(request.folder, term_code=term)

        message = (
            f"Roster for {request.folder.key.course_label} class {class_number} saved to {target}"
        )
        return DownloadRosterResult(saved_path=target, message=message)
