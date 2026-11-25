import json

import pytest

from GAVEL.pages.inspect_grades.correction_store import (
    load_corrections,
    save_corrections,
)


def test_save_and_load_corrections(tmp_path):
    path = tmp_path / "corrections" / "ser222_25sc_12345" / "7216983.json"

    corrections = {
        (100001, "crit_1"): 2.0,
        (100002, "crit_2"): 2.0,
    }

    notes = {
        (100001, "crit_1"): "Adjusted after reviewing the submission.",
        (100002, "crit_2"): "Awarded full credit.",
    }

    save_corrections(path, corrections, notes)

    assert path.is_file()

    loaded_corrections, loaded_notes = load_corrections(path)

    assert loaded_corrections == corrections
    assert loaded_notes == notes


def test_load_missing_corrections_file(tmp_path):
    path = tmp_path / "missing.json"

    corrections, notes = load_corrections(path)

    assert corrections == {}
    assert notes == {}
    assert not path.exists()


def test_saving_replaces_previous_corrections(tmp_path):
    path = tmp_path / "corrections.json"

    save_corrections(
        path,
        {(100002, "crit_2"): 2.0},
        {(100002, "crit_2"): "Awarded full credit."},
    )

    save_corrections(
        path,
        {},
        {},
    )

    scores, notes = load_corrections(path)

    assert scores == {}
    assert notes == {}

    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize(
    "invalid_data",
    [
        [],
        {"version": 2, "corrections": []},
        {"version": 1},
        {"version": 1, "corrections": "invalid"},
        {"version": 1, "corrections": ["invalid"]},
        {
            "version": 1,
            "corrections": [{"student_id": 100002, "criterion_id": "crit_2"}],
        },
    ],
)
def test_load_rejects_invalid_correction_structure(tmp_path, invalid_data):
    path = tmp_path / "invalid_corrections.json"
    path.write_text(json.dumps(invalid_data), encoding="utf-8")

    with pytest.raises(ValueError):
        load_corrections(path)


@pytest.mark.parametrize(
    "invalid_entry",
    [
        {"student_id": "abc", "criterion_id": "crit_2", "corrected_score": 2},
        {"student_id": -1, "criterion_id": "crit_2", "corrected_score": 2},
        {"student_id": 100002, "criterion_id": "", "corrected_score": 2},
        {"student_id": 100002, "criterion_id": "crit_2", "corrected_score": -1},
        {"student_id": 100002, "criterion_id": "crit_2", "corrected_score": "abc"},
        {"student_id": 100002, "criterion_id": "crit_2", "corrected_score": float("inf")},
        {
            "student_id": 100002,
            "criterion_id": "crit_2",
            "corrected_score": 2,
            "notes": 123,
        },
    ],
)
def test_load_rejects_invalid_correction_values(tmp_path, invalid_entry):
    path = tmp_path / "invalid_values.json"

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "corrections": [invalid_entry],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_corrections(path)
