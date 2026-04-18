from __future__ import annotations

from pathlib import Path

from GAVEL.app.dtos.roster import RosterRequest
from GAVEL.app.ports.roster_client import RosterClient


def download_roster_to_file(
    client: RosterClient,
    request: RosterRequest,
    destination: Path,
) -> Path:
    csv_text = client.fetch_roster(request)
    normalized = csv_text.replace("\r\n", "\n").replace("\r", "\n")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(normalized, encoding="utf-8")
    return destination
