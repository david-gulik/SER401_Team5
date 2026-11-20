import json
import os
import tempfile
from pathlib import Path


def save_corrections(
    path: Path,
    corrections: dict[tuple[int, str], float],
    notes: dict[tuple[int, str], str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    keys = sorted(set(corrections) | set(notes))

    entries = [
        {
            "student_id": student_id,
            "criterion_id": criterion_id,
            "corrected_score": corrections.get((student_id, criterion_id)),
            "notes": notes.get((student_id, criterion_id), ""),
        }
        for student_id, criterion_id in keys
    ]

    data = {
        "version": 1,
        "corrections": entries,
    }

    content = json.dumps(data, indent=2) + "\n"
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_corrections(
    path: Path,
) -> tuple[dict[tuple[int, str], float], dict[tuple[int, str], str]]:
    if not path.exists():
        return {}, {}

    data = json.loads(path.read_text(encoding="utf-8"))

    corrections = {}
    notes = {}

    for entry in data["corrections"]:
        key = (int(entry["student_id"]), entry["criterion_id"])

        if entry["corrected_score"] is not None:
            corrections[key] = float(entry["corrected_score"])

        if entry.get("notes"):
            notes[key] = entry["notes"]

    return corrections, notes
