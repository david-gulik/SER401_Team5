from __future__ import annotations

import pytest

from GAVEL.app.dtos.canvas_gradebook import (
    CanvasGradebook,
    GradebookAssignmentColumn,
    GradebookStudentRow,
)
from GAVEL.app.usecases.anonymize_gradebook import (
    AnonymizeGradebookRequest,
    AnonymizeGradebookResult,
    AnonymizeGradebookUseCase,
)

REAL_ID_CONSENTED = 1217482318
REAL_ID_NOT_CONSENTED = 1219749063
REAL_ID_UNMAPPED = 1224316977

ANON_ID_CONSENTED = 4242
ANON_ID_NOT_CONSENTED = 5555

ID_MAP = (
    (REAL_ID_CONSENTED, ANON_ID_CONSENTED),
    (REAL_ID_NOT_CONSENTED, ANON_ID_NOT_CONSENTED),
)
CONSENTED_IDS = (REAL_ID_CONSENTED,)

COLUMN_1 = GradebookAssignmentColumn(
    raw_header="Module 3: Activity (7216974)",
    canvas_id=7216974,
    display_name="Module 3: Activity",
    points_possible=10.0,
)

COLUMN_2 = GradebookAssignmentColumn(
    raw_header="Module 4: Cairn (7216973)",
    canvas_id=7216973,
    display_name="Module 4: Cairn",
    points_possible=3.0,
)

ROW_CONSENTED = GradebookStudentRow(
    student_name="Bourque, Bailey",
    canvas_id=REAL_ID_CONSENTED,
    sis_login_id="brbourqu",
    section="TRN-2026Spring-IVECapstone",
    assignment_scores={
        COLUMN_1.raw_header: 8.45,
        COLUMN_2.raw_header: 1.25,
    },
)

ROW_NOT_CONSENTED = GradebookStudentRow(
    student_name="Crain, Lindy",
    canvas_id=REAL_ID_NOT_CONSENTED,
    sis_login_id="lcrain",
    section="TRN-2026Spring-IVECapstone",
    assignment_scores={
        COLUMN_1.raw_header: None,
        COLUMN_2.raw_header: 0.5,
    },
)

ROW_UNMAPPED = GradebookStudentRow(
    student_name="VonWeinstein, Carli",
    canvas_id=REAL_ID_UNMAPPED,
    sis_login_id="cvonwein",
    section="TRN-2026Spring-IVECapstone",
    assignment_scores={
        COLUMN_1.raw_header: 9.4,
        COLUMN_2.raw_header: 4.75,
    },
)

GRADEBOOK = CanvasGradebook(
    columns=(COLUMN_1, COLUMN_2),
    rows=(ROW_CONSENTED, ROW_NOT_CONSENTED, ROW_UNMAPPED),
)


@pytest.fixture
def use_case() -> AnonymizeGradebookUseCase:
    return AnonymizeGradebookUseCase()


@pytest.fixture
def request_single_consented() -> AnonymizeGradebookRequest:
    return AnonymizeGradebookRequest(
        gradebook=CanvasGradebook(
            columns=(COLUMN_1, COLUMN_2),
            rows=(ROW_CONSENTED,),
        ),
        consented_ids=CONSENTED_IDS,
        id_map=ID_MAP,
    )


class TestConsentedStudentIncluded:
    def test_returns_result(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert isinstance(result, AnonymizeGradebookResult)

    def test_consented_student_is_included(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert len(result.gradebook.rows) == 1

    def test_student_name_is_anonymized(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.gradebook.rows[0].student_name == f"Anon{ANON_ID_CONSENTED}, Anon"

    def test_canvas_id_is_replaced_with_anonymous_id(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.gradebook.rows[0].canvas_id == ANON_ID_CONSENTED

    def test_sis_login_id_is_anonymized(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.gradebook.rows[0].sis_login_id == f"aanon{ANON_ID_CONSENTED}"

    def test_section_is_preserved(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.gradebook.rows[0].section == ROW_CONSENTED.section

    def test_assignment_scores_are_preserved(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.gradebook.rows[0].assignment_scores == ROW_CONSENTED.assignment_scores

    def test_columns_are_preserved(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.gradebook.columns == (COLUMN_1, COLUMN_2)

    def test_skipped_count_is_zero(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.skipped_count == 0

    def test_excluded_count_is_zero(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.excluded_count == 0


class TestNonConsentedStudentExcluded:
    def test_non_consented_student_is_excluded(self, use_case):
        request = AnonymizeGradebookRequest(
            gradebook=CanvasGradebook(columns=(COLUMN_1, COLUMN_2), rows=(ROW_NOT_CONSENTED,)),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.gradebook.rows) == 0

    def test_excluded_count_incremented(self, use_case):
        request = AnonymizeGradebookRequest(
            gradebook=CanvasGradebook(columns=(COLUMN_1, COLUMN_2), rows=(ROW_NOT_CONSENTED,)),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.excluded_count == 1


class TestUnmappedStudentSkipped:
    def test_unmapped_student_is_skipped(self, use_case):
        request = AnonymizeGradebookRequest(
            gradebook=CanvasGradebook(columns=(COLUMN_1, COLUMN_2), rows=(ROW_UNMAPPED,)),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.gradebook.rows) == 0

    def test_skipped_count_incremented(self, use_case):
        request = AnonymizeGradebookRequest(
            gradebook=CanvasGradebook(columns=(COLUMN_1, COLUMN_2), rows=(ROW_UNMAPPED,)),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.skipped_count == 1


class TestEmptyInputs:
    def test_empty_rows_returns_empty_result(self, use_case):
        request = AnonymizeGradebookRequest(
            gradebook=CanvasGradebook(columns=(COLUMN_1, COLUMN_2), rows=()),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.gradebook.rows == ()

    def test_empty_rows_zero_counts(self, use_case):
        request = AnonymizeGradebookRequest(
            gradebook=CanvasGradebook(columns=(COLUMN_1, COLUMN_2), rows=()),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.skipped_count == 0
        assert result.excluded_count == 0


class TestSortedOutput:
    def test_output_is_sorted_by_anonymized_student_name(self, use_case):
        request = AnonymizeGradebookRequest(
            gradebook=CanvasGradebook(
                columns=(COLUMN_1, COLUMN_2),
                rows=(ROW_NOT_CONSENTED, ROW_CONSENTED),
            ),
            consented_ids=(REAL_ID_CONSENTED, REAL_ID_NOT_CONSENTED),
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert [row.student_name for row in result.gradebook.rows] == [
            f"Anon{ANON_ID_CONSENTED}, Anon",
            f"Anon{ANON_ID_NOT_CONSENTED}, Anon",
        ]


class TestOutputTypes:
    def test_result_rows_is_tuple(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert isinstance(result.gradebook.rows, tuple)

    def test_result_entries_are_gradebook_rows(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert all(isinstance(row, GradebookStudentRow) for row in result.gradebook.rows)