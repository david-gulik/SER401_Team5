from __future__ import annotations

import pytest

from GAVEL.app.dtos.canvas_consent_form_entry import ConsentFormEntry
from GAVEL.app.usecases.downselect_consented_students import (
    DownselectConsentedStudentsRequest,
    DownselectConsentedStudentsResult,
    DownselectConsentedStudentsUseCase,
)

REAL_ID_CONSENTED = 1217482318
REAL_ID_FALSE_BOOL = 1219749063
REAL_ID_NAME_MISMATCH = 1224316977
REAL_ID_LATEST_ATTEMPT_FALSE = 1234567890
REAL_ID_PARTIAL_NAME_MATCH = 2345678901

ENTRY_CONSENTED = ConsentFormEntry(
    sis_id=REAL_ID_CONSENTED,
    lms_name="Bailey Bourque",
    attempt=1,
    name_response="Bailey Bourque",
    consented=True,
)

ENTRY_FALSE_BOOL = ConsentFormEntry(
    sis_id=REAL_ID_FALSE_BOOL,
    lms_name="Lindy Crain",
    attempt=1,
    name_response="Lindy Crain",
    consented=False,
)

ENTRY_NAME_MISMATCH = ConsentFormEntry(
    sis_id=REAL_ID_NAME_MISMATCH,
    lms_name="Carli VonWeinstein",
    attempt=1,
    name_response="Totally Different Name",
    consented=True,
)

ENTRY_PARTIAL_NAME_MATCH = ConsentFormEntry(
    sis_id=REAL_ID_PARTIAL_NAME_MATCH,
    lms_name="David Gulik",
    attempt=1,
    name_response="David",
    consented=True,
)

ENTRY_OLD_TRUE = ConsentFormEntry(
    sis_id=REAL_ID_LATEST_ATTEMPT_FALSE,
    lms_name="Sam Student",
    attempt=1,
    name_response="Sam Student",
    consented=True,
)

ENTRY_NEW_FALSE = ConsentFormEntry(
    sis_id=REAL_ID_LATEST_ATTEMPT_FALSE,
    lms_name="Sam Student",
    attempt=2,
    name_response="Sam Student",
    consented=False,
)


@pytest.fixture
def use_case() -> DownselectConsentedStudentsUseCase:
    return DownselectConsentedStudentsUseCase()


@pytest.fixture
def request_single_consented() -> DownselectConsentedStudentsRequest:
    return DownselectConsentedStudentsRequest(
        entries=(ENTRY_CONSENTED,),
    )


class TestConsentedStudentIncluded:
    def test_returns_result(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert isinstance(result, DownselectConsentedStudentsResult)

    def test_consented_student_id_is_included(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.consented_ids == (REAL_ID_CONSENTED,)

    def test_included_count_is_one(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.included_count == 1

    def test_excluded_count_is_zero(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.excluded_count == 0


class TestBooleanFalseExcluded:
    def test_false_bool_is_excluded(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_FALSE_BOOL,),
        )
        result = use_case.execute(request)
        assert result.consented_ids == ()

    def test_false_bool_increments_excluded_count(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_FALSE_BOOL,),
        )
        result = use_case.execute(request)
        assert result.excluded_count == 1


class TestNameMismatchExcluded:
    def test_name_mismatch_is_excluded(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_NAME_MISMATCH,),
        )
        result = use_case.execute(request)
        assert result.consented_ids == ()

    def test_name_mismatch_increments_excluded_count(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_NAME_MISMATCH,),
        )
        result = use_case.execute(request)
        assert result.excluded_count == 1


class TestPartialNameMatchIncluded:
    def test_partial_name_match_is_included(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_PARTIAL_NAME_MATCH,),
        )
        result = use_case.execute(request)
        assert result.consented_ids == (REAL_ID_PARTIAL_NAME_MATCH,)

    def test_partial_name_match_increments_included_count(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_PARTIAL_NAME_MATCH,),
        )
        result = use_case.execute(request)
        assert result.included_count == 1


class TestLatestAttemptWins:
    def test_latest_attempt_is_used(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_OLD_TRUE, ENTRY_NEW_FALSE),
        )
        result = use_case.execute(request)
        assert result.consented_ids == ()

    def test_latest_false_attempt_excludes_student(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_OLD_TRUE, ENTRY_NEW_FALSE),
        )
        result = use_case.execute(request)
        assert result.excluded_count == 1


class TestMixedInputs:
    def test_only_valid_consented_students_are_returned(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(
                ENTRY_CONSENTED,
                ENTRY_FALSE_BOOL,
                ENTRY_NAME_MISMATCH,
                ENTRY_PARTIAL_NAME_MATCH,
            ),
        )
        result = use_case.execute(request)
        assert result.consented_ids == (
            REAL_ID_CONSENTED,
            REAL_ID_PARTIAL_NAME_MATCH,
        )

    def test_counts_are_correct_for_mixed_inputs(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(
                ENTRY_CONSENTED,
                ENTRY_FALSE_BOOL,
                ENTRY_NAME_MISMATCH,
                ENTRY_PARTIAL_NAME_MATCH,
            ),
        )
        result = use_case.execute(request)
        assert result.included_count == 2
        assert result.excluded_count == 2


class TestEmptyInputs:
    def test_empty_entries_returns_empty_result(self, use_case):
        request = DownselectConsentedStudentsRequest(entries=())
        result = use_case.execute(request)
        assert result.consented_ids == ()

    def test_empty_entries_zero_counts(self, use_case):
        request = DownselectConsentedStudentsRequest(entries=())
        result = use_case.execute(request)
        assert result.included_count == 0
        assert result.excluded_count == 0


class TestOutputTypes:
    def test_result_ids_is_tuple(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert isinstance(result.consented_ids, tuple)

    def test_result_ids_are_ints(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert all(isinstance(sis_id, int) for sis_id in result.consented_ids)
