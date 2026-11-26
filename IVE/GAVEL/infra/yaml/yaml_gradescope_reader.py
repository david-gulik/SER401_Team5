from pathlib import Path

from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.ports.gradescope_reader import GradescopeReader
from GAVEL.infra.yaml.gradescope_metadata import load_gradescope_metadata


class YamlGradescopeReader(GradescopeReader):
    """Prototype reader for Gradescope YAML exports."""

    def read(self, path: Path) -> list[GradescopeSubmission]:
        data = load_gradescope_metadata(path)

        submissions = []

        for submission_key, submission_obj in data.items():
            submitter_data = submission_obj[":submitters"][0]

            submitter = GradescopeSubmitter(
                sid=str(submitter_data[":sid"]),
                email=str(submitter_data[":email"]),
                name=str(submitter_data[":name"]),
            )

            tests = [
                GradescopeTestScore(
                    name=test["name"],
                    score=float(test["score"]),
                    max_score=test.get("max_score"),
                    number=test.get("number"),
                )
                for test in submission_obj.get(":results", {}).get("tests", [])
            ]

            submissions.append(
                GradescopeSubmission(
                    submission_key=submission_key,
                    submitter=submitter,
                    created_at=submission_obj[":created_at"],
                    tests=tests,
                    output=submission_obj.get(":results", {}).get("output"),
                )
            )

        return submissions
