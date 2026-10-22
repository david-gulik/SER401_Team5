"""Run slow work off the GUI thread and hear back on it."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

# run_in_background's shape, for view models that take a runner they can swap in tests.
BackgroundRunner = Callable[
    [Callable[[], object], Callable[[object], None], Callable[[Exception], None]], None
]


class _Signals(QObject):
    result = pyqtSignal(object)
    error = pyqtSignal(object)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self._fn = fn
        self.signals = _Signals()

    def run(self) -> None:
        try:
            value = self._fn()
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(exc)
        else:
            self.signals.result.emit(value)


# Tasks still running; their signal objects must outlive the call that started them.
_running: set[_Task] = set()


def run_in_background(
    fn: Callable[[], object],
    on_result: Callable[[object], None],
    on_error: Callable[[Exception], None],
) -> None:
    """Run ``fn`` on the shared thread pool; ``on_result``/``on_error`` run on the GUI thread."""
    task = _Task(fn)
    task.setAutoDelete(False)
    _running.add(task)

    def finish(callback: Callable[[object], None], value: object) -> None:
        _running.discard(task)
        callback(value)

    task.signals.result.connect(lambda value: finish(on_result, value))
    task.signals.error.connect(lambda exc: finish(on_error, exc))
    QThreadPool.globalInstance().start(task)


def run_now(
    fn: Callable[[], object],
    on_result: Callable[[object], None],
    on_error: Callable[[Exception], None],
) -> None:
    """Same contract as run_in_background, but on the calling thread. For tests."""
    try:
        value = fn()
    except Exception as exc:  # noqa: BLE001
        on_error(exc)
    else:
        on_result(value)
