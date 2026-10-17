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
            raw = file.read()

        normalized = re.sub(r"^(\s*):(\w+):", r"\1\2:", raw, flags=re.MULTILINE)
        data = yaml.safe_load(normalized)
        downselected = []

        for key, submission in data.items():
            if not key.startswith("submission_"):
                continue

            submitters = submission.get("submitters")
            filtered_submitters = []
            if not isinstance(submitters, list):
                print(f"Warning: {key} has no valid submitters list")
                downselected.append(key)
                downselected_count += 1
                continue

            sids = set()
            for s in submitters:
                sid = int(s.get("sid"))
                if sid is None:
                    print(f"Warning: submitter missing SID in {key}")
                    continue
                sids.add(sid)

            if sids.isdisjoint(consented):
                downselected.append(key)
                downselected_count += 1
                break

            # Rewrite sid, anonymize name and email
            s["sid"] = id_map[sid]
            s[":name"] = f"Anon {id_map[sid]}"
            s["email"] = "anon@asu.edu"
            filtered_submitters.append(s)

            # Only update if not marked for deletion
            if key not in downselected:
                submission["submitters"] = filtered_submitters
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
