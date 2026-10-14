from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
import re

import yaml

@dataclass(frozen=True)
class AnonymizeGradescopeYMLRequest:
    """
    Request object for anonymizing a Gradescope YML
    """
    input_YML: Path
    consented_ids: tuple[int, ...]
    id_map: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class AnonymizeGradescopeYMLResult:
    """
    Result object containing processed and downselected submissions
    """
    processed_count: int
    downselected_count: int

class AnonymizeGradescopeYMLUseCase:
    """
    Use case for anonymizing Gradescope YML
    """
    def execute(self, request: AnonymizeGradescopeYMLRequest) -> AnonymizeGradescopeYMLResult:


        id_map = dict(request.id_map)
        consented = set(request.consented_ids)

        with open(request.input_YML, 'r', encoding='utf-8') as file:
            raw = file.read()

        normalized = re.sub(r'^(\s*):(\w+):', r'\1\2:', raw, flags=re.MULTILINE)
        data = yaml.safe_load(normalized)
        yaml.dump(data, sys.stdout, default_flow_style=False)
