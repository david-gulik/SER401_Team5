from PyQt6.QtCore import Qt

from GAVEL.app.dtos.rubric_assessment import (
    RubricAssessment,
    RubricCriterionScore,
)
from GAVEL.app.dtos.rubric_definition import (
    RubricCriterionDefinition,
    RubricDefinition,
)
from GAVEL.pages.inspect_grades.student_grade_matrix import StudentGradeMatrix


def make_rubric(criterion_count=3):
    criteria = tuple(
        RubricCriterionDefinition(
            id=f"criterion_{i}",
            description=f"Criterion {i + 1}",
            long_description="",
            points=4.0,
            ratings=(),
        )
        for i in range(criterion_count)
    )

    return RubricDefinition(
        rubric_id="rubric_1",
        title="Test Rubric",
        points_possible=criterion_count * 4.0,
        free_form_criterion_comments=False,
        criteria=criteria,
    )


def make_assessment(student_id, points):
    criteria = tuple(
        RubricCriterionScore(
            criterion_id=f"criterion_{i}",
            points=score,
            comments="",
        )
        for i, score in enumerate(points)
    )

    return RubricAssessment(
        student_id=student_id,
        submission_id=student_id,
        criteria=criteria,
    )


def test_matrix_displays_student_scores(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    rubric = make_rubric()
    assessments = (
        make_assessment(101, [4.0, 3.0, 2.0]),
        make_assessment(102, [2.0, 4.0, 1.0]),
    )

    matrix.display(assessments, rubric)

    assert matrix.table.rowCount() == 2
    assert matrix.table.columnCount() == 7

    assert matrix.table.item(0, 0).text() == "101"
    assert matrix.table.item(0, 1).text() == "9"
    assert matrix.table.item(0, 2).text() == "—"
    assert matrix.table.item(0, 3).text() == "—"

    assert matrix.table.item(0, 4).text() == "4"
    assert matrix.table.item(0, 5).text() == "3"
    assert matrix.table.item(0, 6).text() == "2"

    assert matrix.table.item(1, 0).text() == "102"
    assert matrix.table.item(1, 1).text() == "7"

    matrix.deleteLater()


def test_matrix_distinguishes_zero_and_missing_scores(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    rubric = make_rubric()
    assessments = (make_assessment(101, [4.0, 0.0, None]),)

    matrix.display(assessments, rubric)

    assert matrix.table.item(0, 1).text() == "4 (partial)"
    assert matrix.table.item(0, 4).text() == "4"
    assert matrix.table.item(0, 5).text() == "0"
    assert matrix.table.item(0, 6).text() == "—"

    matrix.deleteLater()


def test_matrix_supports_more_than_15_criteria(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    rubric = make_rubric(18)
    assessments = (make_assessment(101, [4.0] * 18),)

    matrix.display(assessments, rubric)

    assert matrix.table.columnCount() == 22
    assert matrix.table.horizontalHeaderItem(4).text() == "C1"
    assert matrix.table.horizontalHeaderItem(21).text() == "C18"
    assert matrix.table.item(0, 21).text() == "4"
    assert matrix.table.item(0, 1).text() == "72"

    matrix.deleteLater()


def test_matrix_clears_previous_data(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    matrix.display(
        (make_assessment(101, [4.0, 3.0, 2.0]),),
        make_rubric(),
    )

    assert matrix.table.rowCount() == 1

    matrix.clear()

    assert matrix.table.rowCount() == 0
    assert matrix.table.columnCount() == 0

    matrix.deleteLater()


def test_matrix_supports_large_classes(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    rubric = make_rubric(18)
    assessments = tuple(
        make_assessment(student_id, [4.0] * 18) for student_id in range(100001, 100301)
    )

    matrix.display(assessments, rubric)

    assert matrix.table.rowCount() == 300
    assert matrix.table.columnCount() == 22

    assert matrix.table.item(0, 0).text() == "100001"
    assert matrix.table.item(299, 0).text() == "100300"
    assert matrix.table.item(299, 21).text() == "4"

    assert matrix.table.horizontalScrollBarPolicy() != (Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    assert matrix.table.verticalScrollBarPolicy() != (Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    matrix.deleteLater()
