from pathlib import Path
from typing import List

import yaml

from GAVEL.app.dtos.gradescope import (
    GradescopeSubmission,
    GradescopeSubmitter,
    GradescopeTestScore
)
from GAVEL.app.ports.gradescope_reader import GradescopeReader


class YamlGradescopeReader(GradescopeReader):
    """Prototype reader for Gradescope YAML exports."""

    def read(self, path: Path) -> List[GradescopeSubmission]:
        data = yaml.safe_load(path.read_text())

        submissions = []

        for submission_key, submission_obj in data.items():
            submitter_data = submission_obj[":submitters"][0]

            submitter = GradescopeSubmitter(
                sid=str(submitter_data[":sid"]),
                email=str(submitter_data[":email"]),
                name=str(submitter_data[":name"])
            )

            tests = [
                GradescopeTestScore(
                    name=test["name"],
                    score=float(test["score"]),
                    max_score=test.get("max_score"),
                    number=test.get("number"),
                )
                for test in submission_obj[":results"]["tests"]
            ]

            submissions.append(
                GradescopeSubmission(
                    submission_key=submission_key,
                    submitter=submitter,
                    created_at=submission_obj[":created_at"],
                    tests=tests,
                )
            )

        return submissions
