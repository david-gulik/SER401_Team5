from __future__ import annotations

import os
from pathlib import Path

from GAVEL.infra.canvas.http_canvas_client import CanvasApiConfig, HttpCanvasClient


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    course_id = int(os.getenv("CANVAS_COURSE_ID", "253450"))
    token = require_env("CANVAS_API_TOKEN")
    base_url = os.getenv("CANVAS_BASE_URL", "https://canvas.asu.edu")
    account_id = 1

    config = CanvasApiConfig(
        base_url=base_url,
        token=token,
        account_id=account_id,
    )

    client = HttpCanvasClient(config)

    print(f"Fetching gradebook CSV for course {course_id}...")
    csv_bytes = client.fetch_gradebook_csv(course_id)

    output_path = Path("test_gradebook.csv")
    output_path.write_bytes(csv_bytes)

    print(f"Wrote {output_path.resolve()}")
    print(f"Size: {len(csv_bytes)} bytes")


if __name__ == "__main__":
    main()