from __future__ import annotations

import time
from collections.abc import Callable

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from GAVEL.app.progress import DownloadProgress
from GAVEL.theme.context import ThemeContext
from GAVEL.ui_components.layout import set_spacing


def format_duration(seconds: float) -> str:
    """1:42 style, or 1:02:05 past an hour."""
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_remaining(seconds: float) -> str:
    """A rough time left; precision would be false given how uneven items are."""
    if seconds < 60:
        return "under a minute left"
    minutes = round(seconds / 60)
    return f"about {minutes} min left"


class ProgressPanel(QFrame):
    """Big, readable progress for a long batch: what is running, how far, how long.

    Hidden until ``show_progress``; ``clear`` hides it again. Elapsed time
    counts from the first report after a ``clear``. The time-left estimate
    uses the pace of the current batch (a new label or total starts a new
    batch) and only appears once one item has finished.
    """

    def __init__(
        self,
        theme: ThemeContext,
        parent: QWidget | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self.setProperty("role", "progress_panel")
        self._clock = clock
        self._started_at: float | None = None
        self._batch: tuple[str, int] | None = None
        self._batch_started_at = 0.0
        self._progress: DownloadProgress | None = None

        self._title = QLabel()
        self._title.setProperty("role", "progress_title")
        self._title.setWordWrap(True)
        self._count = QLabel()
        self._count.setProperty("role", "progress_count")

        self._bar = QProgressBar()
        self._bar.setProperty("role", "progress_bar")
        self._bar.setTextVisible(False)
        self._percent = QLabel()
        self._percent.setProperty("role", "progress_percent")

        self._detail = QLabel()
        self._detail.setProperty("role", "progress_detail")
        self._detail.setWordWrap(True)
        self._timing = QLabel()
        self._timing.setProperty("role", "progress_detail")

        header = QHBoxLayout()
        set_spacing(header, theme, 8)
        header.addWidget(self._title, 1)
        header.addWidget(self._count)

        bar_row = QHBoxLayout()
        set_spacing(bar_row, theme, 8)
        bar_row.addWidget(self._bar, 1)
        bar_row.addWidget(self._percent)

        footer = QHBoxLayout()
        set_spacing(footer, theme, 12)
        footer.addWidget(self._detail, 1)
        footer.addWidget(self._timing)

        root = QVBoxLayout(self)
        root.setContentsMargins(
            theme.tokens.sp(12), theme.tokens.sp(8), theme.tokens.sp(12), theme.tokens.sp(8)
        )
        set_spacing(root, theme, 4)
        root.addLayout(header)
        root.addLayout(bar_row)
        root.addLayout(footer)

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._refresh_timing)
        self.hide()

    def show_progress(self, progress: DownloadProgress) -> None:
        now = self._clock()
        if self._started_at is None:
            self._started_at = now
        batch = (progress.label, progress.total)
        if batch != self._batch:
            self._batch = batch
            self._batch_started_at = now
        self._progress = progress

        counted = progress.total > 0
        self._title.setText(progress.label)
        self._count.setText(f"{progress.done} of {progress.total}" if counted else "")
        self._count.setVisible(counted)
        if counted:
            self._bar.setRange(0, progress.total)
            self._bar.setValue(progress.done)
            self._percent.setText(f"{progress.done * 100 // progress.total}%")
        else:
            self._bar.setRange(0, 0)
        self._percent.setVisible(counted)
        self._detail.setText(f"Last finished: {progress.item}" if progress.item else "")
        self._detail.setVisible(bool(progress.item))
        self._refresh_timing()

        if not self._ticker.isActive():
            self._ticker.start()
        self.show()

    def clear(self) -> None:
        self._ticker.stop()
        self._started_at = None
        self._batch = None
        self._progress = None
        self.hide()

    def _refresh_timing(self) -> None:
        if self._started_at is None or self._progress is None:
            return
        now = self._clock()
        text = f"{format_duration(now - self._started_at)} elapsed"
        p = self._progress
        if p.total > 0 and 0 < p.done < p.total:
            per_item = (now - self._batch_started_at) / p.done
            text += f" · {format_remaining(per_item * (p.total - p.done))}"
        self._timing.setText(text)

    # Exposed for tests.

    @property
    def title_text(self) -> str:
        return self._title.text()

    @property
    def count_text(self) -> str:
        return self._count.text()

    @property
    def percent_text(self) -> str:
        return self._percent.text()

    @property
    def detail_text(self) -> str:
        return self._detail.text()

    @property
    def timing_text(self) -> str:
        return self._timing.text()

    @property
    def bar(self) -> QProgressBar:
        return self._bar
