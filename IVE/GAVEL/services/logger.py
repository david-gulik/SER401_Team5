from __future__ import annotations

import logging


class AppLogger:
    def __init__(self, name: str = "GAVEL", propagate: bool = True) -> None:
        self._logger = logging.getLogger(name)
        self._logger.propagate = propagate
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            fmt = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
            handler.setFormatter(fmt)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)

    def error(self, msg: str) -> None:
        self._logger.error(msg)
