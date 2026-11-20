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
