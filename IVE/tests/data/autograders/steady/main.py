"""Fixture autograder that gives the same result every run.

Grades ``source/answer.txt``: full marks on the first test when it holds 42,
fixed scores on the other two whatever the submission says.
"""

import json
from pathlib import Path

answer = (Path("source") / "answer.txt").read_text(encoding="utf-8").strip()
print(f"grading answer {answer!r}")

results = {
    "tests": [
        {
            "name": "Adds two numbers",
            "score": 2.0 if answer == "42" else 0.0,
            "max_score": 2.0,
            "output": "ok" if answer == "42" else f"expected 42, got {answer}",
        },
        {
            "name": "Handles negatives",
            "score": 1.0,
            "max_score": 2.0,
            "output": "expected -3, got -2",
        },
        {"name": "Prints the total", "score": 1.0, "max_score": 1.0, "output": "ok"},
    ]
}
Path("results").mkdir(exist_ok=True)
(Path("results") / "results.json").write_text(json.dumps(results), encoding="utf-8")
