from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AnonymizeGradescopeYMLRequest:
    """
    Request object for anonymizing a Gradescope YML
    """

    input_YML: Path
    consented_ids: tuple[int, ...]
    id_map: tuple[tuple[int, int], ...]
    output_YML: Path


@dataclass(frozen=True)
class AnonymizeGradescopeYMLResult:
    """
    Result object containing processed and downselected submissions
    """

    processed_count: int
    downselected_count: int
    output_YML: Path


class AnonymizeGradescopeYMLUseCase:
    """
    Use case for anonymizing Gradescope YML
    """

    def execute(self, request: AnonymizeGradescopeYMLRequest) -> AnonymizeGradescopeYMLResult:

        # TODO: preserve original yaml formatting
        # class LiteralString(str):
        #     pass
        #
        # def literal_representer(dumper, data):
        #     return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        #
        # yaml.add_representer(LiteralString, literal_representer)

        id_map = dict(request.id_map)
        consented = set(request.consented_ids)
        processed_count = 0
        downselected_count = 0

        with open(request.input_YML, encoding="utf-8") as file:
            data = yaml.safe_load(file)

        downselected = []

        for key, submission in data.items():
            if not key.startswith("submission_"):
                continue

            submitters = submission.get(":submitters")
            if not isinstance(submitters, list):
                print(f"Warning: {key} has no valid submitters list")
                downselected.append(key)
                downselected_count += 1
                continue

            # Collect SIDs safely
            sids = set()
            for s in submitters:
                sid_raw = s.get(":sid")
                if sid_raw is None:
                    print(f"Warning: submitter missing SID in {key}")
                    continue
                try:
                    sid = int(sid_raw)
                except ValueError:
                    print(f"Warning: non-integer SID in {key}: {sid_raw}")
                    continue
                sids.add(sid)

            # If none of the submitters are consented → delete whole submission
            if sids.isdisjoint(consented):
                downselected.append(key)
                downselected_count += 1
                continue

            # Otherwise anonymize ALL submitters
            filtered_submitters = []
            for s in submitters:
                sid_raw = s.get(":sid")
                if sid_raw is None:
                    continue
                sid = int(sid_raw)

                # Rewrite sid, anonymize name/email
                s[":sid"] = id_map[sid]
                s[":name"] = f"Anon {id_map[sid]}"
                s[":email"] = "anon@asu.edu"

                filtered_submitters.append(s)

            submission[":submitters"] = filtered_submitters
            processed_count += 1

        for key in downselected:
            del data[key]

        with open(request.output_YML, "w") as file:
            yaml.dump(data, file, default_flow_style=False)

        return AnonymizeGradescopeYMLResult(
            processed_count=processed_count,
            downselected_count=downselected_count,
            output_YML=request.output_YML,
        )
