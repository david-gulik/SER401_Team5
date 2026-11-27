"""The autograder runner port, implemented on the parallel autograder client.

One call grades one submission folder with one autograder folder exactly the
way ``grade_one_submission`` does for the Autograders page, but hands back the
scores and the reason for any failure instead of leaving a JSON file behind.
The client's results land in a scratch folder that is removed afterwards.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from GAVEL.app.dtos.autograder_run import AutograderRunOutcome, AutograderRunStatus
from GAVEL.app.dtos.gradescope import GradescopeTestScore
from GAVEL.app.ports.autograder_runner import AutograderRunner
from GAVEL.infra.autograders.parallel_autograder_client import (
    AutograderRunFailed,
    _detect_language,
    _remove_worker,
    grade_one_submission,
)

CONFIG_FILE = "config.json"


class LocalAutograderRunner(AutograderRunner):
    def __init__(self, output_tail_chars: int = 2000) -> None:
        self._output_tail_chars = output_tail_chars

    def run(
        self,
        submission_dir: Path,
        autograder_dir: Path,
        timeout_seconds: float | None = None,
    ) -> AutograderRunOutcome:
        submission_dir = Path(submission_dir)
        autograder_dir = Path(autograder_dir)
        started = time.perf_counter()
        output_dir = Path(tempfile.mkdtemp(prefix="autograder_results_"))
        try:
            try:
                config = json.loads((autograder_dir / CONFIG_FILE).read_text(encoding="utf-8"))
                if "files_required" not in config and "required_files" in config:
                    config["files_required"] = config["required_files"]
            except (OSError, ValueError) as exc:
                return self._crashed(
                    started, "", f"Could not read {CONFIG_FILE} in {autograder_dir}: {exc}"
                )

            try:
                grade_one_submission(
                    submission_dir.name,
                    config,
                    _detect_language(submission_dir),
                    str(autograder_dir),
                    str(submission_dir.parent),
                    str(output_dir),
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                return AutograderRunOutcome(
                    status=AutograderRunStatus.TIMED_OUT,
                    duration_seconds=time.perf_counter() - started,
                    output_tail=self._tail(_as_text(exc.stdout) + _as_text(exc.stderr)),
                    error=f"Stopped after {timeout_seconds} seconds",
                )
            except AutograderRunFailed as exc:
                return self._crashed(
                    started,
                    self._tail(_as_text(exc.stdout) + _as_text(exc.stderr)),
                    f"{exc}: {_last_line(_as_text(exc.stderr))}",
                )
            except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
                return self._crashed(started, "", f"{type(exc).__name__}: {exc}")

            stem = submission_dir.name.split(".")[0]
            log_path = output_dir / f"{stem}_stdout.txt"
            output = ""
            if log_path.is_file():
                output = self._tail(log_path.read_text(encoding="utf-8", errors="replace"))
            try:
                tests = _read_results(output_dir / f"{stem}.json")
            except (OSError, ValueError, KeyError, TypeError) as exc:
                return self._crashed(started, output, f"Results could not be read: {exc}")

            return AutograderRunOutcome(
                status=AutograderRunStatus.COMPLETED,
                duration_seconds=time.perf_counter() - started,
                tests=tests,
                output_tail=output,
            )
        finally:
            _remove_worker(str(output_dir))

    def _tail(self, output: str) -> str:
        keep = self._output_tail_chars
        return output[-keep:]

    def _crashed(self, started: float, output: str, error: str) -> AutograderRunOutcome:
        return AutograderRunOutcome(
            status=AutograderRunStatus.CRASHED,
            duration_seconds=time.perf_counter() - started,
            output_tail=output,
            error=error,
        )


def _read_results(path: Path) -> tuple[GradescopeTestScore, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tests = data.get("tests") if isinstance(data, dict) else None
    if not isinstance(tests, list):
        raise ValueError("no tests list")
    scores = []
    for entry in tests:
        max_score = entry.get("max_score")
        scores.append(
            GradescopeTestScore(
                name=str(entry["name"]),
                score=float(entry.get("score", 0.0)),
                max_score=float(max_score) if max_score is not None else None,
                number=entry.get("number"),
            )
        )
    return tuple(scores)


def _as_text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _last_line(text: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1].strip() if lines else "no error output"
