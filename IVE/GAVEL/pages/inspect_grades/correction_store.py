import json
import math
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

    if not isinstance(data, dict):
        raise ValueError("Correction file must contain a JSON object.")

    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Unsupported correction file version.")

    if not isinstance(data.get("corrections"), list):
        raise ValueError("Correction file must contain a corrections list.")

    corrections = {}
    notes = {}

    for entry in data["corrections"]:
        if not isinstance(entry, dict):
            raise ValueError("Each correction entry must be an object.")

        if not all(field in entry for field in ("student_id", "criterion_id", "corrected_score")):
            raise ValueError("Correction entry is missing required fields.")

        student_id = entry["student_id"]
        criterion_id = entry["criterion_id"]
        score = entry["corrected_score"]
        note = entry.get("notes", "")

        if type(student_id) is not int or student_id <= 0:
            raise ValueError("Correction entry has an invalid student ID.")

        if not isinstance(criterion_id, str) or not criterion_id.strip():
            raise ValueError("Correction entry has an invalid criterion ID.")

        if score is not None:
            if type(score) not in (int, float):
                raise ValueError("Corrected score must be a number.")

            if not math.isfinite(score) or score < 0:
                raise ValueError("Corrected score must be finite and non-negative.")

        if not isinstance(note, str):
            raise ValueError("Correction notes must be text.")

        key = (student_id, criterion_id)

        if score is not None:
            corrections[key] = float(score)

        if note:
            notes[key] = note

    return corrections, notes
