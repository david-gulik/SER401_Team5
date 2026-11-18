from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from GAVEL.app.dtos.autograder_run import AutograderRunOutcome, AutograderRunStatus
from GAVEL.infra.autograders.local_autograder_runner import LocalAutograderRunner
from GAVEL.infra.autograders.parallel_autograder_client import (
    AutograderRunFailed,
    grade_one_submission,
)

AUTOGRADERS = Path(__file__).resolve().parents[2] / "data" / "autograders"


def _score(outcome: AutograderRunOutcome, test_name: str) -> float:
    [test] = [t for t in outcome.tests if t.name == test_name]
    return test.score


def _scratch_folders() -> set[str]:
    temp = Path(tempfile.gettempdir())
    return {p.name for p in temp.iterdir() if p.name.startswith("autograder_")}


@pytest.fixture
def submission(tmp_path: Path) -> Path:
    folder = tmp_path / "anon_4821"
    folder.mkdir()
    (folder / "answer.txt").write_text("42", encoding="utf-8")
    return folder


@pytest.fixture
def runner() -> LocalAutograderRunner:
    return LocalAutograderRunner()


def test_a_completed_run_returns_every_test_score(runner, submission):
    outcome = runner.run(submission, AUTOGRADERS / "steady", timeout_seconds=60)

    assert outcome.status is AutograderRunStatus.COMPLETED
    assert outcome.completed
    assert [(t.name, t.score, t.max_score) for t in outcome.tests] == [
        ("Adds two numbers", 2.0, 2.0),
        ("Handles negatives", 1.0, 2.0),
        ("Prints the total", 1.0, 1.0),
    ]
    assert outcome.duration_seconds > 0
    assert "grading answer '42'" in outcome.output_tail
    assert outcome.error is None


def test_the_autograder_sees_the_submission(runner, tmp_path):
    folder = tmp_path / "anon_1093"
    folder.mkdir()
    (folder / "answer.txt").write_text("7", encoding="utf-8")

    outcome = runner.run(folder, AUTOGRADERS / "steady", timeout_seconds=60)

    assert _score(outcome, "Adds two numbers") == 0.0


def test_a_flaky_autograder_changes_its_result_between_runs(
    runner, submission, tmp_path, monkeypatch
):
    monkeypatch.setenv("GAVEL_FLAKY_COUNTER", str(tmp_path / "counter"))
    monkeypatch.setenv("GAVEL_FLAKY_PERIOD", "2")

    outcomes = [runner.run(submission, AUTOGRADERS / "flaky", timeout_seconds=60) for _ in range(3)]

    assert [_score(o, "Handles negatives") for o in outcomes] == [2.0, 0.0, 2.0]
    assert all(_score(o, "Adds two numbers") == 2.0 for o in outcomes)


def test_a_hung_autograder_times_out_at_the_limit(runner, submission):
    outcome = runner.run(submission, AUTOGRADERS / "hang", timeout_seconds=0.5)

    assert outcome.status is AutograderRunStatus.TIMED_OUT
    assert not outcome.completed
    assert outcome.tests == ()
    assert outcome.duration_seconds >= 0.5
    assert outcome.error == "Stopped after 0.5 seconds"


def test_a_crashing_autograder_is_crashed_with_its_message(runner, submission):
    outcome = runner.run(submission, AUTOGRADERS / "crash", timeout_seconds=60)

    assert outcome.status is AutograderRunStatus.CRASHED
    assert outcome.tests == ()
    assert outcome.error == "main.py exited with status 3: boom: the compiler exploded"
    assert "compiling..." in outcome.output_tail
    assert "boom" in outcome.output_tail


def test_an_autograder_that_writes_no_results_is_crashed(runner, submission, tmp_path):
    autograder = tmp_path / "silent"
    autograder.mkdir()
    (autograder / "config.json").write_text(
        json.dumps({"project_location": "source/", "files_required": ["answer.txt"]}),
        encoding="utf-8",
    )
    (autograder / "main.py").write_text("print('done')\n", encoding="utf-8")

    outcome = runner.run(submission, autograder, timeout_seconds=60)

    assert outcome.status is AutograderRunStatus.CRASHED
    assert outcome.error == "main.py exited with status 0: no error output"


def test_an_autograder_without_a_config_is_crashed(runner, submission, tmp_path):
    autograder = tmp_path / "bare"
    autograder.mkdir()

    outcome = runner.run(submission, autograder, timeout_seconds=60)

    assert outcome.status is AutograderRunStatus.CRASHED
    assert outcome.error is not None
    assert outcome.error.startswith("Could not read config.json")


def test_the_workspace_folders_are_left_untouched(runner, submission):
    before = sorted(p.name for p in (AUTOGRADERS / "steady").iterdir())

    runner.run(submission, AUTOGRADERS / "steady", timeout_seconds=60)

    assert sorted(p.name for p in (AUTOGRADERS / "steady").iterdir()) == before
    assert sorted(p.name for p in submission.iterdir()) == ["answer.txt"]


def test_scratch_copies_are_removed(runner, submission):
    before = _scratch_folders()

    runner.run(submission, AUTOGRADERS / "steady", timeout_seconds=60)
    runner.run(submission, AUTOGRADERS / "crash", timeout_seconds=60)
    runner.run(submission, AUTOGRADERS / "hang", timeout_seconds=0.5)

    assert _scratch_folders() - before == set()


def test_the_client_still_writes_its_files_for_the_autograders_page(submission, tmp_path):
    output = tmp_path / "evaluations"
    output.mkdir()
    config = json.loads((AUTOGRADERS / "steady" / "config.json").read_text(encoding="utf-8"))

    message = grade_one_submission(
        submission.name,
        config,
        None,
        str(AUTOGRADERS / "steady"),
        str(submission.parent),
        str(output),
    )

    assert message.startswith("anon_4821: done")
    written = json.loads((output / "anon_4821.json").read_text(encoding="utf-8"))
    assert [t["name"] for t in written["tests"]][0] == "Adds two numbers"
    assert "grading answer '42'" in (output / "anon_4821_stdout.txt").read_text(encoding="utf-8")


def test_the_client_raises_with_the_output_when_the_autograder_fails(submission, tmp_path):
    output = tmp_path / "evaluations"
    output.mkdir()
    config = json.loads((AUTOGRADERS / "crash" / "config.json").read_text(encoding="utf-8"))

    with pytest.raises(AutograderRunFailed) as caught:
        grade_one_submission(
            submission.name,
            config,
            None,
            str(AUTOGRADERS / "crash"),
            str(submission.parent),
            str(output),
        )

    assert caught.value.returncode == 3
    assert "compiling..." in caught.value.stdout
    assert "boom" in caught.value.stderr
