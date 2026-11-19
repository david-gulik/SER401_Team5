"""Fixture autograder whose second test changes its mind between runs.

"Handles negatives" normally earns full marks but fails on a schedule. A test
sets ``GAVEL_FLAKY_COUNTER`` to a file path and ``GAVEL_FLAKY_PERIOD`` to N so
every Nth run (counted in that file) fails; without them the test flips a coin.
"""

import json
import os
import random
from pathlib import Path

counter_path = os.environ.get("GAVEL_FLAKY_COUNTER")
if counter_path:
    counter = Path(counter_path)
    run_number = int(counter.read_text(encoding="utf-8") or "0") + 1 if counter.exists() else 1
    counter.write_text(str(run_number), encoding="utf-8")
    period = int(os.environ.get("GAVEL_FLAKY_PERIOD", "2"))
    fails = run_number % period == 0
else:
    fails = random.random() < 0.5

print("negatives test " + ("failed" if fails else "passed"))

results = {
    "tests": [
        {"name": "Adds two numbers", "score": 2.0, "max_score": 2.0, "output": "ok"},
        {
            "name": "Handles negatives",
            "score": 0.0 if fails else 2.0,
            "max_score": 2.0,
            "output": "expected -3, got -2" if fails else "ok",
        },
        {"name": "Prints the total", "score": 1.0, "max_score": 1.0, "output": "ok"},
    ]
}
Path("results").mkdir(exist_ok=True)
(Path("results") / "results.json").write_text(json.dumps(results), encoding="utf-8")
