from __future__ import annotations

from PyQt6.QtCore import QThreadPool

from GAVEL.core.background import run_in_background, run_now


def settle(qapp) -> None:
    QThreadPool.globalInstance().waitForDone()
    for _ in range(10):
        qapp.processEvents()


def test_result_comes_back_on_the_gui_thread(qapp):
    seen = []

    run_in_background(lambda: 41 + 1, seen.append, seen.append)
    settle(qapp)

    assert seen == [42]


def test_exception_goes_to_on_error(qapp):
    errors = []

    def boom():
        raise ValueError("bad data")

    run_in_background(boom, lambda _: None, errors.append)
    settle(qapp)

    assert [str(e) for e in errors] == ["bad data"]


def test_run_now_has_the_same_contract():
    results, errors = [], []

    run_now(lambda: "ok", results.append, errors.append)
    run_now(lambda: 1 / 0, results.append, errors.append)

    assert results == ["ok"]
    assert isinstance(errors[0], ZeroDivisionError)
