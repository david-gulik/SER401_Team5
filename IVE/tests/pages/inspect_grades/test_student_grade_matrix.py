from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from GAVEL.app.dtos.rubric_assessment import (
    RubricAssessment,
    RubricCriterionScore,
)
from GAVEL.app.dtos.rubric_definition import (
    RubricCriterionDefinition,
    RubricDefinition,
)
from GAVEL.pages.inspect_grades.student_grade_matrix import (
    ComparisonCellDelegate,
    StudentGradeMatrix,
)


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


def test_matrix_highlights_matches_and_mismatches(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    rubric = make_rubric()
    assessments = (make_assessment(101, [4.0, 3.0, None]),)

    proxy_scores = {
        101: {
            "criterion_0": 4.0,
            "criterion_1": 4.0,
            "criterion_2": 2.0,
        }
    }

    matrix.display(
        assessments,
        rubric,
        proxy_scores_by_student=proxy_scores,
    )

    assert matrix.table.item(0, 4).text() == "4/4"
    assert matrix.table.item(0, 5).text() == "3/4"
    assert matrix.table.item(0, 6).text() == "—/2"

    assert matrix.table.item(0, 4).background().color() == QColor("#246B48")
    assert matrix.table.item(0, 5).background().color() == QColor("#913D45")
    assert "Match: 1" in matrix.legend_label.text()
    assert "Mismatch: 1" in matrix.legend_label.text()

    assert matrix.table.item(0, 6).background().style() == Qt.BrushStyle.NoBrush

    matrix.deleteLater()


def test_matrix_displays_proxy_total_and_difference(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    assessments = (make_assessment(101, [4.0, 3.0, 2.0]),)
    proxy_scores = {
        101: {
            "criterion_0": 4.0,
            "criterion_1": 4.0,
            "criterion_2": 2.0,
        }
    }

    matrix.display(
        assessments,
        make_rubric(),
        proxy_scores_by_student=proxy_scores,
    )

    assert matrix.table.item(0, 1).text() == "9"
    assert matrix.table.item(0, 2).text() == "10"
    assert matrix.table.item(0, 3).text() == "-1"

    matrix.deleteLater()


def test_matrix_hides_difference_for_incomplete_grades(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    assessments = (
        make_assessment(101, [4.0, None, 2.0]),
        make_assessment(102, [4.0, 3.0, 2.0]),
    )
    proxy_scores = {
        101: {
            "criterion_0": 4.0,
            "criterion_1": 3.0,
            "criterion_2": 2.0,
        },
        102: {
            "criterion_0": 4.0,
            "criterion_1": 3.0,
        },
    }

    matrix.display(
        assessments,
        make_rubric(),
        proxy_scores_by_student=proxy_scores,
    )

    assert matrix.table.item(0, 1).text() == "6 (partial)"
    assert matrix.table.item(0, 2).text() == "9"
    assert matrix.table.item(0, 3).text() == "—"

    assert matrix.table.item(1, 1).text() == "9"
    assert matrix.table.item(1, 2).text() == "—"
    assert matrix.table.item(1, 3).text() == "—"

    matrix.deleteLater()


def test_matrix_filters_students_by_id(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    assessments = (
        make_assessment(100001, [4.0, 2.0, 1.0]),
        make_assessment(100002, [3.0, 1.0, 2.0]),
        make_assessment(200003, [4.0, 4.0, 4.0]),
    )

    matrix.display(assessments, make_rubric())

    assert matrix.table.rowCount() == 3

    matrix.search_input.setText("1000")

    assert not matrix.table.isRowHidden(0)
    assert not matrix.table.isRowHidden(1)
    assert matrix.table.isRowHidden(2)

    matrix.search_input.setText("100002")

    assert matrix.table.isRowHidden(0)
    assert not matrix.table.isRowHidden(1)
    assert matrix.table.isRowHidden(2)

    matrix.search_input.clear()

    assert all(not matrix.table.isRowHidden(row) for row in range(matrix.table.rowCount()))

    matrix.deleteLater()


def test_matrix_filters_only_mismatched_students(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    assessments = (
        make_assessment(100001, [4.0, 2.0, 1.0]),
        make_assessment(100002, [3.0, 3.0, 1.0]),
        make_assessment(100003, [4.0, 2.0, 1.0]),
    )

    proxy_scores = {
        100001: {
            "criterion_0": 4.0,
            "criterion_1": 2.0,
            "criterion_2": 1.0,
        },
        100002: {
            "criterion_0": 4.0,
            "criterion_1": 2.0,
            "criterion_2": 1.0,
        },
    }

    matrix.display(
        assessments,
        make_rubric(),
        proxy_scores_by_student=proxy_scores,
    )

    matrix.mismatch_checkbox.setChecked(True)

    assert matrix.table.isRowHidden(0)
    assert not matrix.table.isRowHidden(1)
    assert matrix.table.isRowHidden(2)

    assert matrix.table.item(1, 3).text() == "0"

    matrix.mismatch_checkbox.setChecked(False)

    assert all(not matrix.table.isRowHidden(row) for row in range(3))

    matrix.deleteLater()


def test_search_and_mismatch_filter_work_together(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    assessments = (
        make_assessment(100001, [4.0, 2.0, 1.0]),
        make_assessment(100002, [3.0, 2.0, 1.0]),
        make_assessment(200003, [2.0, 2.0, 1.0]),
    )

    proxy_scores = {
        100001: {
            "criterion_0": 4.0,
            "criterion_1": 2.0,
            "criterion_2": 1.0,
        },
        100002: {
            "criterion_0": 4.0,
            "criterion_1": 2.0,
            "criterion_2": 1.0,
        },
        200003: {
            "criterion_0": 4.0,
            "criterion_1": 2.0,
            "criterion_2": 1.0,
        },
    }

    matrix.display(
        assessments,
        make_rubric(),
        proxy_scores_by_student=proxy_scores,
    )

    matrix.search_input.setText("1000")
    matrix.mismatch_checkbox.setChecked(True)

    assert matrix.table.isRowHidden(0)
    assert not matrix.table.isRowHidden(1)
    assert matrix.table.isRowHidden(2)

    matrix.search_input.clear()

    assert matrix.table.isRowHidden(0)
    assert not matrix.table.isRowHidden(1)
    assert not matrix.table.isRowHidden(2)

    matrix.deleteLater()


def test_matrix_uses_comparison_cell_delegate(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    assert isinstance(
        matrix.table.itemDelegate(),
        ComparisonCellDelegate,
    )

    matrix.deleteLater()


def test_matrix_shows_message_when_filters_hide_all_students(qapp, theme):
    matrix = StudentGradeMatrix(theme)

    matrix.display(
        (make_assessment(100001, [4.0, 2.0, 1.0]),),
        make_rubric(),
    )

    matrix.search_input.setText("999999")

    assert matrix.table.isRowHidden(0)
    assert not matrix.empty_label.isHidden()

    matrix.search_input.clear()

    assert not matrix.table.isRowHidden(0)
    assert matrix.empty_label.isHidden()

    matrix.deleteLater()
