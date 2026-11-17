from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from GAVEL.app.dtos.autograder_run import AutograderRunOutcome


class AutograderRunner(ABC):
    """Runs one autograder on one submission and reports how it went.

    A runner never raises for anything the autograder does: a hang becomes a
    timed-out outcome, a crash or missing results becomes a crashed outcome.
    Callers that run many executions can therefore keep going and count them.
    """

    @abstractmethod
    def run(
        self,
        submission_dir: Path,
        autograder_dir: Path,
        timeout_seconds: float | None = None,
    ) -> AutograderRunOutcome:
        """Grade the submission folder with the autograder folder.

        ``timeout_seconds`` caps one execution; ``None`` means no limit. Neither
        folder is modified: the runner works on its own copies.
        """
        raise NotImplementedError
