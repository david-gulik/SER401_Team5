from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook, GradebookStudentRow
from GAVEL.app.dtos.gradescope import GradescopeSubmission, GradescopeSubmitter, GradescopeTestScore
from GAVEL.app.dtos.proxy_grade_mapping import Criterion, ProxyGradeMapping, Tier
from GAVEL.app.dtos.rubric_assessment import RubricAssessment, RubricCriterionScore
from GAVEL.app.dtos.rubric_definition import RubricCriterionDefinition, RubricDefinition
from GAVEL.app.ports.gradescope_reader import GradescopeReader
from GAVEL.app.usecases.proxy_grade.generate_heat_map_report import (
    GenerateHeatMapReportRequest,
    GenerateHeatMapReportUseCase,
    HeatMapScoreRow,
)

# A small two-criterion mapping, named to match the rubric fixture below.
_MAPPING = ProxyGradeMapping(
    name="toy",
    criteria=(
        Criterion("main menu", (Tier(2.0, all_of=("Test A", "Test B")),)),
        Criterion("memory leaks", (Tier(2.0, all_of=("Test C",)),)),
    ),
)
_ALL_TEST_NAMES = list(_MAPPING.test_names())
_GRADEBOOK_COLUMN = "Module 2: Programming (123456)"


def _rubric_criterion(cid: str, description: str) -> RubricCriterionDefinition:
    return RubricCriterionDefinition(
        id=cid, description=description, long_description="", points=2.0, ratings=()
    )


_RUBRIC = RubricDefinition(
    rubric_id="1",
    title="toy rubric",
    points_possible=4.0,
    free_form_criterion_comments=False,
    criteria=(
        _rubric_criterion("c1", "main menu"),
        _rubric_criterion("c2", "memory leaks"),
    ),
)


def _submission(sid: str, email: str, passing: set[str]) -> GradescopeSubmission:
    tests = [
        GradescopeTestScore(name=name, score=1.0 if name in passing else 0.0, max_score=1.0)
        for name in _ALL_TEST_NAMES
    ]
    return GradescopeSubmission(
        submission_key=f"submission_{sid}",
        submitter=GradescopeSubmitter(sid=sid, email=email, name="Test Student"),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        tests=tests,
    )


def _assessment(student_id: int, scores: dict[str, float]) -> RubricAssessment:
    return RubricAssessment(
        student_id=student_id,
        submission_id=student_id,
        criteria=tuple(
            RubricCriterionScore(criterion_id=cid, points=points, comments="")
            for cid, points in scores.items()
        ),
    )


class FakeGradescopeReader(GradescopeReader):
    def __init__(self, by_path: dict[Path, list[GradescopeSubmission]]) -> None:
        self._by_path = by_path

    def read(self, path: Path) -> list[GradescopeSubmission]:
        return self._by_path[path]


class FakeGradebookReader:
    def __init__(self, gradebook: CanvasGradebook) -> None:
        self._gradebook = gradebook

    def parse(self, path: Path) -> CanvasGradebook:
        return self._gradebook


class FakeRubricDefinitionReader:
    def __init__(self, definition: RubricDefinition) -> None:
        self._definition = definition

    def read(self, path: Path) -> RubricDefinition:
        return self._definition


class FakeRubricAssessmentReader:
    def __init__(self, assessments: list[RubricAssessment]) -> None:
        self._assessments = assessments

    def read(self, path: Path) -> tuple[RubricAssessment, ...]:
        return tuple(self._assessments)


def test_reads_submissions_a_gradebook_and_a_rubric_and_writes_a_report(
    tmp_path: Path,
) -> None:
    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    yaml_path = submissions_dir / "student1.yml"
    yaml_path.write_text("placeholder")

    submission = _submission("1", "student1@asu.edu", set(_ALL_TEST_NAMES))
    gradebook = CanvasGradebook(
        columns=(),
        rows=(
            GradebookStudentRow(
                student_name="One, Student",
                canvas_id=1,
                sis_login_id="student1",
                section="001",
                assignment_scores={_GRADEBOOK_COLUMN: 4.0},
            ),
        ),
    )
    assessments = [_assessment(1, {"c1": 1.0, "c2": 2.0})]
    output_path = tmp_path / "report.json"

    use_case = GenerateHeatMapReportUseCase(
        gradescope_reader=FakeGradescopeReader({yaml_path: [submission]}),
        gradebook_reader=FakeGradebookReader(gradebook),
        rubric_definition_reader=FakeRubricDefinitionReader(_RUBRIC),
        rubric_assessment_reader=FakeRubricAssessmentReader(assessments),
    )

    result = use_case.execute(
        GenerateHeatMapReportRequest(
            submissions_dir=submissions_dir,
            mapping=_MAPPING,
            gradebook_path=tmp_path / "gradebook.csv",
            rubric_definition_path=tmp_path / "rubric_definition.json",
            rubric_assessments_path=tmp_path / "rubric_assessments.json",
            output_path=output_path,
        )
    )

    assert result.unmatched_submissions == ()
    assert set(result.rows) == {
        HeatMapScoreRow("student1", "main menu", human_points=1.0, proxy_points=2.0),
        HeatMapScoreRow("student1", "memory leaks", human_points=2.0, proxy_points=2.0),
    }
    assert output_path.exists()


def test_submission_with_no_matching_gradebook_row_is_reported_as_unmatched(
    tmp_path: Path,
) -> None:
    submissions_dir = tmp_path / "submissions"
    submissions_dir.mkdir()
    yaml_path = submissions_dir / "student2.yml"
    yaml_path.write_text("placeholder")

    submission = _submission("2", "nobody@asu.edu", set())

    use_case = GenerateHeatMapReportUseCase(
        gradescope_reader=FakeGradescopeReader({yaml_path: [submission]}),
        gradebook_reader=FakeGradebookReader(CanvasGradebook(columns=(), rows=())),
        rubric_definition_reader=FakeRubricDefinitionReader(_RUBRIC),
        rubric_assessment_reader=FakeRubricAssessmentReader([]),
    )

    result = use_case.execute(
        GenerateHeatMapReportRequest(
            submissions_dir=submissions_dir,
            mapping=_MAPPING,
            gradebook_path=tmp_path / "gradebook.csv",
            rubric_definition_path=tmp_path / "rubric_definition.json",
            rubric_assessments_path=tmp_path / "rubric_assessments.json",
            output_path=tmp_path / "report.json",
        )
    )

    assert result.rows == ()
    assert result.unmatched_submissions == ("2",)
