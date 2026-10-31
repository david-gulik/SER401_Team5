"""Progress reports for downloads that fetch many items one after another."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class DownloadProgress:
    """How far a batch download has got: ``done`` of ``total`` items have finished.

    ``item`` names the item that just finished, for the status message. A
    ``total`` of 0 means the count is not known yet.
    """

    label: str
    done: int
    total: int
    item: str | None = None

    @property
    def text(self) -> str:
        """Short form for a progress bar, e.g. "Downloading quizzes 10 of 22"."""
        if self.total <= 0:
            return self.label
        return f"{self.label} {self.done} of {self.total}"


ProgressCallback = Callable[[DownloadProgress], None]


def report(
    on_progress: ProgressCallback | None,
    label: str,
    done: int,
    total: int,
    item: str | None = None,
) -> None:
    """Send one progress report, if anyone is listening."""
    if on_progress is not None:
        on_progress(DownloadProgress(label=label, done=done, total=total, item=item))
