from __future__ import annotations

import json
from pathlib import Path


def read_signed_errors(path: Path) -> tuple[float, ...]:
    """Reads the signed error of each scored row in a signed-error report.

    Only the values are returned. Student identifiers stay in the file, so
    nothing downstream of this reader can display them.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(float(row["signed_error"]) for row in payload["rows"])
