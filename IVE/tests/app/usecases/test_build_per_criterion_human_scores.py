from __future__ import annotations

import pytest

from GAVEL.app.dtos.rubric_assessment import RubricAssessment, RubricCriterionScore
from GAVEL.app.dtos.rubric_definition import (
    RubricCriterionDefinition,
    RubricDefinition,
    RubricRating,
)
from GAVEL.app.usecases.anonymize_rubric_assessment import (
    AnonymizeRubricAssessmentRequest,
    AnonymizeRubricAssessmentUseCase,
)
from GAVEL.app.usecases.build_per_criterion_human_scores import (
    UnknownRubricCriterionError,
    build_per_criterion_human_scores,
)


def _definition() -> RubricDefinition:
    def criterion(cid: str, description: str, points: float) -> RubricCriterionDefinition:
        rating = RubricRating(id=f"{cid}_r", description="", long_description="", points=points)
        return RubricCriterionDefinition(
            id=cid,
            description=description,
            long_description="",
            points=points,
            ratings=(rating,),
        )

    return RubricDefinition(
        rubric_id="r1",
        title="Test rubric",
        points_possible=3.0,
        free_form_criterion_comments=False,
        criteria=(
            criterion("c_a", "main menu", 2.0),
            criterion("c_b", "memory leaks", 1.0),
        ),
    )


def _assessment(
    student_id: int, points_a: float | None, points_b: float | None
) -> RubricAssessment:
    return RubricAssessment(
        student_id=student_id,
        submission_id=1,
        criteria=(
            RubricCriterionScore(criterion_id="c_a", points=points_a, comments=""),
            RubricCriterionScore(criterion_id="c_b", points=points_b, comments=""),
        ),
    )


def test_joins_criterion_names_and_points_from_the_definition() -> None:
    rows = build_per_criterion_human_scores(_definition(), [_assessment(1001, 2.0, 0.5)])

    assert [(r.student_id, r.criterion, r.points, r.points_possible) for r in rows] == [
        (1001, "main menu", 2.0, 2.0),
        (1001, "memory leaks", 0.5, 1.0),
    ]


def test_rows_follow_the_rubric_criterion_order_for_each_student() -> None:
    rows = build_per_criterion_human_scores(
        _definition(),
        [_assessment(1002, 1.0, 1.0), _assessment(1001, 2.0, 0.0)],
    )

    assert [(r.student_id, r.criterion) for r in rows] == [
        (1002, "main menu"),
        (1002, "memory leaks"),
        (1001, "main menu"),
        (1001, "memory leaks"),
    ]


def test_a_missing_points_value_is_kept_as_none() -> None:
    rows = build_per_criterion_human_scores(_definition(), [_assessment(1001, None, 1.0)])

    assert rows[0].points is None
    assert rows[0].points_possible == 2.0


def test_a_criterion_absent_from_an_assessment_produces_no_row() -> None:
    assessment = RubricAssessment(
        student_id=1001,
        submission_id=1,
        criteria=(RubricCriterionScore(criterion_id="c_a", points=2.0, comments=""),),
    )

    rows = build_per_criterion_human_scores(_definition(), [assessment])

    assert [r.criterion for r in rows] == ["main menu"]


def test_an_unknown_criterion_id_is_reported_by_name() -> None:
    assessment = RubricAssessment(
        student_id=1001,
        submission_id=1,
        criteria=(RubricCriterionScore(criterion_id="c_zzz", points=1.0, comments=""),),
    )

    with pytest.raises(UnknownRubricCriterionError) as error:
        build_per_criterion_human_scores(_definition(), [assessment])

    assert error.value.unknown == ("c_zzz",)


def test_student_ids_match_the_shared_anonymized_id_map() -> None:
    # The anonymized gradebook uses the same map for SIS User ID, so rubric rows
    # must carry exactly those anonymized IDs for the consented students.
    id_map = {2001: 4321, 2002: 5555, 2003: 7777}
    assessments = (
        RubricAssessment(
            student_id=2001,
            submission_id=10,
            criteria=(RubricCriterionScore(criterion_id="c_a", points=2.0, comments="x"),),
        ),
        RubricAssessment(
            student_id=2002,
            submission_id=11,
            criteria=(RubricCriterionScore(criterion_id="c_a", points=1.0, comments="y"),),
        ),
        RubricAssessment(
            student_id=2003,
            submission_id=12,
            criteria=(RubricCriterionScore(criterion_id="c_a", points=0.0, comments="z"),),
        ),
    )
    anonymized = AnonymizeRubricAssessmentUseCase().execute(
        AnonymizeRubricAssessmentRequest(
            assessments=assessments,
            consented_ids=(2001, 2002),
            id_map=tuple(id_map.items()),
        )
    )

    rows = build_per_criterion_human_scores(_definition(), list(anonymized.assessments))

    assert {r.student_id for r in rows} == {4321, 5555}
    assert anonymized.excluded_count == 1
