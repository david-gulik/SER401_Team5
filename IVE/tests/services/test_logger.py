from __future__ import annotations

import logging

from GAVEL.services.logger import AppLogger


def test_propagating_logger_adds_no_handler_of_its_own():
    AppLogger("GAVEL.test_propagating")

    assert logging.getLogger("GAVEL.test_propagating").handlers == []


def test_non_propagating_logger_prints_through_its_own_handler():
    AppLogger("GAVEL.test_isolated", propagate=False)

    logger = logging.getLogger("GAVEL.test_isolated")
    assert logger.propagate is False
    assert len(logger.handlers) == 1
