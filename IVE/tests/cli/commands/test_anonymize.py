import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

from GAVEL.cli.commands.anonymize import handle_anonymize_run


def make_context():
    ctx = Mock()
    ctx.logger = Mock()
    return ctx


def test_missing_dataset_directory_returns_2(
    tmp_path: Path,
    capsys,
):
    ctx = make_context()

    args = Namespace(
        dataset_dir=str(tmp_path / "does-not-exist"),
    )

    result = handle_anonymize_run(ctx, args)

    captured = capsys.readouterr()

    assert result == 2
    assert "Dataset directory does not exist" in captured.err


def test_missing_consent_form_returns_2(
    tmp_path: Path,
    capsys,
):
    ctx = make_context()

    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()

    args = Namespace(
        dataset_dir=str(snapshot_dir),
    )

    result = handle_anonymize_run(ctx, args)

    captured = capsys.readouterr()

    assert result == 2
    assert "Consent form is missing from the dataset" in captured.err


def write_consent_form(snapshot_dir: Path) -> None:
    original_dir = snapshot_dir / "original"
    original_dir.mkdir(parents=True, exist_ok=True)

    (original_dir / "consent_form.csv").write_text(
        "sis_id,name,attempt,leave blank if your name is correct,Do you consent\n"
        "100001,Test Student,1,Test Student,True\n",
        encoding="utf-8",
    )


def write_roster(snapshot_dir: Path) -> None:
    (snapshot_dir / "original" / "roster.csv").write_text(
        "ID,Posting ID,First Name,Last Name,Status,Units,"
        "Grade Basis,Program and Plan,Academic Level,ASURITE,"
        "Residency,Zoom Email\n"
        "100001,100001-001,Test,Student,Enrolled,3,"
        "GRD,SER,Senior,teststudent,Resident,test@example.com\n",
        encoding="utf-8",
    )


def write_gradebook(snapshot_dir: Path) -> None:
    (snapshot_dir / "original" / "gradebook.csv").write_text(
        "Student,ID,SIS Login ID,Section,Module 1: Assignment (7216983)\n"
        "Manual Posting,,,,\n"
        "Points Possible,,,,10\n"
        '"Test Student",100001,teststudent,SER 401,9\n',
        encoding="utf-8",
    )


def write_rubric(snapshot_dir: Path) -> None:
    assignment_dir = snapshot_dir / "original" / "assignments" / "7216983_m1"
    assignment_dir.mkdir(parents=True, exist_ok=True)

    (assignment_dir / "rubric_assessment_12345_7216983.json").write_text(
        json.dumps(
            [
                {
                    "student_id": 100001,
                    "submission_id": 9001,
                    "criteria": [
                        {
                            "criterion_id": "crit_1",
                            "points": 4.0,
                            "comments": "Good work",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )


def test_successful_run_returns_0_and_prints_summary(
    tmp_path: Path,
    capsys,
):
    ctx = make_context()

    snapshot_dir = tmp_path / "snapshot"

    write_consent_form(snapshot_dir)
    write_roster(snapshot_dir)
    write_gradebook(snapshot_dir)
    write_rubric(snapshot_dir)

    args = Namespace(
        dataset_dir=str(snapshot_dir),
    )

    result = handle_anonymize_run(ctx, args)

    captured = capsys.readouterr()

    assert result == 0
    assert "Anonymized dataset written to" in captured.out
    assert "Consent form:" in captured.out
    assert "Roster:" in captured.out
    assert "Gradebook:" in captured.out
    assert "Rubric assessments:" in captured.out

    assert (snapshot_dir / "anonymized" / "consent_form.csv").exists()
    assert (snapshot_dir / "anonymized" / "roster.csv").exists()
    assert (snapshot_dir / "anonymized" / "gradebook.csv").exists()

    assert (
        snapshot_dir
        / "anonymized"
        / "assignments"
        / "7216983_m1"
        / "rubric_assessment_12345_7216983.json"
    ).exists()
