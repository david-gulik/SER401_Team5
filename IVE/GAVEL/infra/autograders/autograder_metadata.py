import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from GAVEL.core.status import Status
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.status_pill import StatusPill


@dataclass
class AutograderInfo:
    path: Path
    name: str

    last_run: datetime | None = None
    duration_seconds: float | None = None
    has_run: bool = True
    last_status: str = "unknown"

    @property
    def metadata_file(self) -> Path:
        return self.path / "metadata.json"


DEFAULT_METADATA = {
    "has_run": False,
    "duration_seconds": None,
    "last_run": None,
    "last_status": "never_run",
}


def load_autograder(folder: Path) -> AutograderInfo:
    metadata_file = folder / "metadata.json"
    # print(metadata_file)

    if not metadata_file.exists():
        with open(metadata_file, "w") as f:
            json.dump(DEFAULT_METADATA, f, indent=4)

    with open(metadata_file) as f:
        data = json.load(f)

    autograder = AutograderInfo(
        path=folder,
        name=folder.name,
    )

    autograder.has_run = data.get("has_run")
    # autograder.run_count = data.get("run_count", 0)
    autograder.duration_seconds = data.get("duration_seconds")
    # print(autograder.last_run)
    autograder.last_status = data.get("last_status", "never_run")

    if data.get("last_run"):
        autograder.last_run = datetime.fromisoformat(data["last_run"])

    return autograder


def save_autograder_metadata(autograder: AutograderInfo) -> None:
    metadata_file = autograder.path / "metadata.json"

    data = {
        "has_run": autograder.has_run,
        "duration_seconds": autograder.duration_seconds,
        "last_status": autograder.last_status,
        "last_run": (autograder.last_run.isoformat() if autograder.last_run else None),
    }

    with open(metadata_file, "w") as f:
        json.dump(data, f, indent=4)


def load_metadata(autograder: AutograderInfo) -> None:
    metadata_file = autograder.path / "metadata.json"

    if not metadata_file.exists():
        return

    with open(metadata_file) as f:
        data = json.load(f)

    autograder.has_run = data.get("has_run", False)
    autograder.run_count = data.get("run_count", 0)
    autograder.duration_seconds = data.get("duration_seconds")

    if data.get("last_run"):
        autograder.last_run = datetime.fromisoformat(data["last_run"])

    autograder.last_status = data.get("last_status", "unknown")


def save_metadata(autograder: AutograderInfo) -> None:
    metadata_file = autograder.path / "metadata.json"

    data = {
        "has_run": autograder.has_run,
        "run_count": autograder.run_count,
        "duration_seconds": autograder.duration_seconds,
        "last_status": autograder.last_status,
        "last_run": (autograder.last_run.isoformat() if autograder.last_run else None),
    }

    with open(metadata_file, "w") as f:
        json.dump(data, f, indent=4)


class AutograderRow(QWidget):
    def __init__(self, theme: ThemeContext, autograder: AutograderInfo, parent=None):
        super().__init__(parent)

        self.autograder = autograder

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.checkbox = QCheckBox(autograder.name)

        self.status = StatusPill(theme, Status.UNKNOWN)

        self.metadata = QLabel()
        self.metadata.setProperty("role", "text_muted")

        layout.addWidget(self.checkbox)
        layout.addWidget(self.status)
        layout.addWidget(self.metadata)
        layout.addStretch()

        self.refresh()

    def refresh(self) -> None:
        if not self.autograder.has_run:
            self.status.set_status(Status.UNKNOWN)
            self.metadata.setText("Never run")
            return

        self.status.set_status(Status.UNKNOWN)

        self.metadata.setText(
            f"Last run: {self.autograder.last_run} ({self.autograder.duration_seconds:.2f}s)"
        )

        if self.autograder.last_status == "never_run":
            self.status.set_status(Status.UNKNOWN)
            self.metadata.setText("Never run")

        elif self.autograder.last_status == "success":
            self.status.set_status(Status.NOMINAL)

        elif self.autograder.last_status == "failure":
            self.status.set_status(Status.WARNING)

            self.metadata.setText("Most recent run failed")

    @property
    def is_checked(self) -> bool:
        return self.checkbox.isChecked()
