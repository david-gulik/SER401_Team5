from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SignedErrorWithIdentity:
    """One student's signed error paired with their anonymized identifier.

    Note: tested with fixtures, but will not work against real data until
    anonymize_course_dataset.py writes an anonymized submission_metadata.yml
    into anonymized/. The anonymized data should be written to that location.
    """

    student_identifier: str
    signed_error: float


def read_signed_errors(path: Path) -> tuple[float, ...]:
    """Reads the signed error of each scored row in a signed-error report.

    Only the signed_error values are returned, with no student identifier
    attached to any of them. Use read_signed_errors_with_identity to read
    the identifier alongside each value.

    Raises ValueError, naming the file, if it is not a signed-error report
    (e.g. a heat map report was chosen instead).
    """
    return tuple(item.signed_error for item in read_signed_errors_with_identity(path))


def read_signed_errors_with_identity(path: Path) -> tuple[SignedErrorWithIdentity, ...]:
    """Reads each scored row's signed error paired with its anonymized student identifier.

    Raises ValueError, naming the file, if it is not a signed-error report
    (e.g. a heat map report was chosen instead).
    """
    rows = _report_rows(path)
    try:
        return tuple(
            SignedErrorWithIdentity(
                student_identifier=str(row["student_identifier"]),
                signed_error=float(row["signed_error"]),
            )
            for row in rows
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path.name} is not a signed-error report ({exc}).") from exc


def _report_rows(path: Path) -> list:
    """Reads a report file's 'rows' list common to every report reader in this module."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise ValueError(f"{path.name} is not a report file (missing 'rows').")
    return payload["rows"]
