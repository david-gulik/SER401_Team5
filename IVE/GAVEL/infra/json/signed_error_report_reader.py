from __future__ import annotations

import json
from pathlib import Path


def read_signed_errors(path: Path) -> tuple[float, ...]:
    """Reads the signed error of each scored row in a signed-error report.

    Only the values are returned. Student identifiers stay in the file, so
    nothing downstream of this reader can display them.

    Raises ValueError, naming the file, if it is not a signed-error report
    (e.g. a heat map report was chosen instead).
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise ValueError(f"{path.name} is not a report file (missing 'rows').")
    try:
        return tuple(float(row["signed_error"]) for row in payload["rows"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path.name} is not a signed-error report ({exc}).") from exc
