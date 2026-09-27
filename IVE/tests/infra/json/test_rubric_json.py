"""Round trips for the rubric JSON codec and compatibility with files the
rubric download use case already writes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from GAVEL.app.dtos.rubric_assessment import RubricAssessment, RubricCriterionScore
from GAVEL.app.dtos.rubric_definition import (
    RubricCriterionDefinition,
    RubricDefinition,
    RubricRating,
)
from GAVEL.app.ports.rubric_assessment_reader import RubricAssessmentReader
from GAVEL.app.ports.rubric_definition_reader import RubricDefinitionReader
from GAVEL.app.usecases.download_rubric_assessment import (
    DownloadRubricAssessmentRequest,
    DownloadRubricAssessmentUseCase,
)
from GAVEL.infra.json.rubric_json import (
    assessment_from_dict,
    assessment_to_dict,
    assessments_from_json,
    assessments_to_json,
    definition_from_dict,
    definition_from_json,
    definition_to_dict,
    definition_to_json,
)
from GAVEL.infra.json.rubric_json_reader import (
    JsonRubricAssessmentReader,
    JsonRubricDefinitionReader,
)
from tests.app.usecases.test_download_rubric_assessment import (
    ASSIGNMENT_ID,
    COURSE_ID,
    RUBRIC_ASSESSMENTS,
    RUBRIC_DEFINITION,
    MockCanvasClient,
)

ASSESSMENT = RubricAssessment(
    student_id=100001,
    submission_id=9001,
    criteria=(
        RubricCriterionScore(criterion_id="crit_1", points=4.0, comments="Good work"),
        RubricCriterionScore(criterion_id="crit_2", points=None, comments=""),
    ),
)

DEFINITION = RubricDefinition(
    rubric_id="rub_1",
    title="Problem Set Rubric",
    points_possible=None,
    free_form_criterion_comments=True,
    criteria=(
        RubricCriterionDefinition(
            id="crit_1",
            description="Correctness",
            long_description="Reaches the right answer.",
            points=4.0,
            ratings=(
                RubricRating(id="r1", description="Full", long_description="", points=4.0),
                RubricRating(id="r2", description="None", long_description="", points=None),
            ),
        ),
        RubricCriterionDefinition(
            id="crit_2", description="Clarity", long_description="", points=None, ratings=()
        ),
    ),
)


class TestAssessmentCodec:
    def test_dict_round_trip(self) -> None:
        assert assessment_from_dict(assessment_to_dict(ASSESSMENT)) == ASSESSMENT

    def test_json_round_trip(self) -> None:
        text = assessments_to_json([ASSESSMENT, ASSESSMENT])
        assert assessments_from_json(text) == (ASSESSMENT, ASSESSMENT)

    def test_dict_shape(self) -> None:
        d = assessment_to_dict(ASSESSMENT)
        assert d == {
            "student_id": 100001,
            "submission_id": 9001,
            "criteria": [
                {"criterion_id": "crit_1", "points": 4.0, "comments": "Good work"},
                {"criterion_id": "crit_2", "points": None, "comments": ""},
            ],
        }

    def test_missing_optional_fields_tolerated(self) -> None:
        a = assessment_from_dict(
            {"student_id": "1", "submission_id": 2, "criteria": [{"criterion_id": "c"}]}
        )
        assert a.criteria[0].points is None
        assert a.criteria[0].comments == ""

    def test_non_array_rejected(self) -> None:
        with pytest.raises(ValueError, match="array"):
            assessments_from_json("{}")


class TestDefinitionCodec:
    def test_dict_round_trip(self) -> None:
        assert definition_from_dict(definition_to_dict(DEFINITION)) == DEFINITION

    def test_json_round_trip(self) -> None:
        assert definition_from_json(definition_to_json(DEFINITION)) == DEFINITION

    def test_dict_shape_top_level(self) -> None:
        d = definition_to_dict(DEFINITION)
        assert set(d) == {
            "rubric_id",
            "title",
            "points_possible",
            "free_form_criterion_comments",
            "criteria",
        }
        assert set(d["criteria"][0]) == {
            "id",
            "description",
            "long_description",
            "points",
            "ratings",
        }
        assert set(d["criteria"][0]["ratings"][0]) == {
            "id",
            "description",
            "long_description",
            "points",
        }

    def test_non_object_rejected(self) -> None:
        with pytest.raises(ValueError, match="object"):
            definition_from_json("[]")


class TestReadersMatchExistingDownloads:
    """Files written by DownloadRubricAssessmentUseCase today load through the readers."""

    @pytest.fixture
    def downloaded(self, tmp_path: Path) -> tuple[Path, Path]:
        result = DownloadRubricAssessmentUseCase(MockCanvasClient()).execute(
            DownloadRubricAssessmentRequest(
                course_id=COURSE_ID, assignment_id=ASSIGNMENT_ID, output_dir=tmp_path
            )
        )
        assert result.definition_saved_path is not None
        return result.saved_path, result.definition_saved_path

    def test_assessments_reader(self, downloaded: tuple[Path, Path]) -> None:
        reader = JsonRubricAssessmentReader()
        assert isinstance(reader, RubricAssessmentReader)
        assert reader.read(downloaded[0]) == tuple(RUBRIC_ASSESSMENTS)

    def test_definition_reader(self, downloaded: tuple[Path, Path]) -> None:
        reader = JsonRubricDefinitionReader()
        assert isinstance(reader, RubricDefinitionReader)
        assert reader.read(downloaded[1]) == RUBRIC_DEFINITION

    def test_codec_output_is_byte_identical_to_use_case_output(
        self, downloaded: tuple[Path, Path]
    ) -> None:
        assert json.loads(downloaded[0].read_text()) == json.loads(
            assessments_to_json(RUBRIC_ASSESSMENTS)
        )
        assert json.loads(downloaded[1].read_text()) == json.loads(
            definition_to_json(RUBRIC_DEFINITION)
        )
