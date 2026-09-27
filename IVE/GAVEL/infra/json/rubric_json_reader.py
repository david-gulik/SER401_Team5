from __future__ import annotations

from pathlib import Path

from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.app.ports.rubric_assessment_reader import RubricAssessmentReader
from GAVEL.app.ports.rubric_definition_reader import RubricDefinitionReader
from GAVEL.infra.json.rubric_json import assessments_from_json, definition_from_json


class JsonRubricAssessmentReader(RubricAssessmentReader):
    """Reads a ``rubric_assessments.json`` written by the rubric download use case."""

    def read(self, path: Path) -> tuple[RubricAssessment, ...]:
        return assessments_from_json(Path(path).read_text(encoding="utf-8"))


class JsonRubricDefinitionReader(RubricDefinitionReader):
    """Reads a ``rubric_definition.json`` written by the rubric download use case."""

    def read(self, path: Path) -> RubricDefinition:
        return definition_from_json(Path(path).read_text(encoding="utf-8"))
