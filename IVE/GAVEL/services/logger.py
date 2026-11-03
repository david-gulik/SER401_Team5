from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"


def configure_logging(level: int = logging.INFO) -> None:
    """Send every logger's records to the terminal once, with a timestamp.

    Call once at startup, before anything logs. Does nothing if the root
    logger already has a handler.
    """
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)


class AppLogger:
    def __init__(self, name: str = "GAVEL", propagate: bool = True) -> None:
        self._logger = logging.getLogger(name)

        # A propagating logger prints through the root handler from
        # configure_logging; a handler of its own would print every line twice.
        if not propagate and not self._logger.handlers:
            self._logger.propagate = False

            handler = logging.StreamHandler()
            fmt = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
            handler.setFormatter(fmt)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)

    def error(self, msg: str) -> None:
        self._logger.error(msg)
