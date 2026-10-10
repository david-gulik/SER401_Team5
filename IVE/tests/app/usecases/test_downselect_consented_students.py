from __future__ import annotations

import pytest

from GAVEL.app.dtos.asu_roster import RosterStudent
from GAVEL.app.dtos.canvas_consent_form_entry import ConsentFormEntry
from GAVEL.app.dtos.consent_decision import ConsentDecision, ConsentStatus
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
REAL_ID_NAME_BLANK = 3456789012
REAL_ID_NO_RESPONSE = 4567890123

CANVAS_ID_CONSENTED = 309780
CANVAS_ID_FALSE_BOOL = 494030
CANVAS_ID_NAME_MISMATCH = 771671
CANVAS_ID_LATEST_ATTEMPT_FALSE = 100001
CANVAS_ID_PARTIAL_NAME_MATCH = 100002
CANVAS_ID_NAME_BLANK = 100003

ENTRY_CONSENTED = ConsentFormEntry(
    canvas_id=CANVAS_ID_CONSENTED,
    sis_id=REAL_ID_CONSENTED,
    lms_name="Bailey Bourque",
    attempt=1,
    name_response="Bailey Bourque",
    consented=True,
)

ENTRY_FALSE_BOOL = ConsentFormEntry(
    canvas_id=CANVAS_ID_FALSE_BOOL,
    sis_id=REAL_ID_FALSE_BOOL,
    lms_name="Lindy Crain",
    attempt=1,
    name_response="Lindy Crain",
    consented=False,
)

ENTRY_NAME_MISMATCH = ConsentFormEntry(
    canvas_id=CANVAS_ID_NAME_MISMATCH,
    sis_id=REAL_ID_NAME_MISMATCH,
    lms_name="Carli VonWeinstein",
    attempt=1,
    name_response="Totally Different Name",
    consented=True,
)

ENTRY_PARTIAL_NAME_MATCH = ConsentFormEntry(
    canvas_id=CANVAS_ID_PARTIAL_NAME_MATCH,
    sis_id=REAL_ID_PARTIAL_NAME_MATCH,
    lms_name="David Gulik",
    attempt=1,
    name_response="David",
    consented=True,
)

ENTRY_OLD_TRUE = ConsentFormEntry(
    canvas_id=CANVAS_ID_LATEST_ATTEMPT_FALSE,
    sis_id=REAL_ID_LATEST_ATTEMPT_FALSE,
    lms_name="Sam Student",
    attempt=1,
    name_response="Sam Student",
    consented=True,
)

ENTRY_NEW_FALSE = ConsentFormEntry(
    canvas_id=CANVAS_ID_LATEST_ATTEMPT_FALSE,
    sis_id=REAL_ID_LATEST_ATTEMPT_FALSE,
    lms_name="Sam Student",
    attempt=2,
    name_response="Sam Student",
    consented=False,
)

ENTRY_NAME_BLANK = ConsentFormEntry(
    canvas_id=CANVAS_ID_NAME_BLANK,
    sis_id=REAL_ID_NAME_BLANK,
    lms_name="Robin Example",
    attempt=1,
    name_response="   ",
    consented=True,
)


def roster_student(sis_id: int, first_name: str, last_name: str) -> RosterStudent:
    return RosterStudent(
        id=str(sis_id),
        posting_id=f"{sis_id}-001",
        first_name=first_name,
        last_name=last_name,
        status="Enrolled",
        units=3,
        grade_basis="GRD",
        program_and_plan="SER",
        academic_level="Senior",
        asurite="example",
        residency="Resident",
        zoom_email="example@example.com",
    )


ROSTER_NO_RESPONSE = roster_student(REAL_ID_NO_RESPONSE, "Quinn", "Absent")
ROSTER_RESPONDED = roster_student(REAL_ID_CONSENTED, "Bailey", "Bourque")


def only_decision(result: DownselectConsentedStudentsResult) -> ConsentDecision:
    assert len(result.decisions) == 1
    return result.decisions[0]


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
        assert result.consented_ids == (CANVAS_ID_CONSENTED,)

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
        assert result.consented_ids == (CANVAS_ID_PARTIAL_NAME_MATCH,)

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
            CANVAS_ID_PARTIAL_NAME_MATCH,
            CANVAS_ID_CONSENTED,
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
        assert all(isinstance(canvas_id, int) for canvas_id in result.consented_ids)


class TestDecisionReasons:
    def test_consented_student_is_included(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert only_decision(result).status is ConsentStatus.INCLUDED

    def test_false_bool_is_declined(self, use_case):
        request = DownselectConsentedStudentsRequest(entries=(ENTRY_FALSE_BOOL,))
        result = use_case.execute(request)
        assert only_decision(result).status is ConsentStatus.DECLINED

    def test_blank_name_response_is_name_blank(self, use_case):
        request = DownselectConsentedStudentsRequest(entries=(ENTRY_NAME_BLANK,))
        result = use_case.execute(request)
        assert only_decision(result).status is ConsentStatus.NAME_BLANK

    def test_blank_name_response_is_excluded(self, use_case):
        request = DownselectConsentedStudentsRequest(entries=(ENTRY_NAME_BLANK,))
        result = use_case.execute(request)
        assert result.consented_ids == ()
        assert result.excluded_count == 1

    def test_different_name_is_name_mismatch(self, use_case):
        request = DownselectConsentedStudentsRequest(entries=(ENTRY_NAME_MISMATCH,))
        result = use_case.execute(request)
        assert only_decision(result).status is ConsentStatus.NAME_MISMATCH

    def test_partial_name_match_is_included(self, use_case):
        request = DownselectConsentedStudentsRequest(entries=(ENTRY_PARTIAL_NAME_MATCH,))
        result = use_case.execute(request)
        assert only_decision(result).status is ConsentStatus.INCLUDED

    def test_latest_attempt_decides_the_reason(self, use_case):
        request = DownselectConsentedStudentsRequest(entries=(ENTRY_OLD_TRUE, ENTRY_NEW_FALSE))
        result = use_case.execute(request)
        decision = only_decision(result)
        assert decision.status is ConsentStatus.DECLINED
        assert decision.attempt == 2

    def test_decision_carries_the_student_and_their_answers(self, use_case):
        request = DownselectConsentedStudentsRequest(entries=(ENTRY_NAME_MISMATCH,))
        result = use_case.execute(request)
        assert only_decision(result) == ConsentDecision(
            sis_id=REAL_ID_NAME_MISMATCH,
            name="Carli VonWeinstein",
            status=ConsentStatus.NAME_MISMATCH,
            canvas_id=CANVAS_ID_NAME_MISMATCH,
            attempt=1,
            name_response="Totally Different Name",
            consented=True,
        )


class TestRosterNoResponse:
    def test_roster_student_without_consent_entry_is_no_response(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_CONSENTED,),
            roster=(ROSTER_RESPONDED, ROSTER_NO_RESPONSE),
        )
        result = use_case.execute(request)
        no_response = [
            decision
            for decision in result.decisions
            if decision.status is ConsentStatus.NO_RESPONSE
        ]
        assert no_response == [
            ConsentDecision(
                sis_id=REAL_ID_NO_RESPONSE,
                name="Quinn Absent",
                status=ConsentStatus.NO_RESPONSE,
            )
        ]

    def test_roster_student_who_responded_is_not_duplicated(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_CONSENTED,),
            roster=(ROSTER_RESPONDED,),
        )
        result = use_case.execute(request)
        assert only_decision(result).status is ConsentStatus.INCLUDED

    def test_no_response_is_not_counted_as_excluded(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(ENTRY_CONSENTED,),
            roster=(ROSTER_NO_RESPONSE,),
        )
        result = use_case.execute(request)
        assert result.consented_ids == (CANVAS_ID_CONSENTED,)
        assert result.included_count == 1
        assert result.excluded_count == 0

    def test_roster_only_produces_only_no_response(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(),
            roster=(ROSTER_NO_RESPONSE,),
        )
        result = use_case.execute(request)
        assert only_decision(result).status is ConsentStatus.NO_RESPONSE
        assert result.consented_ids == ()


class TestDecisionList:
    def test_one_decision_per_student_sorted_by_name(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(
                ENTRY_NAME_BLANK,
                ENTRY_CONSENTED,
                ENTRY_OLD_TRUE,
                ENTRY_NEW_FALSE,
                ENTRY_NAME_MISMATCH,
            ),
            roster=(ROSTER_NO_RESPONSE,),
        )
        result = use_case.execute(request)
        assert [decision.name for decision in result.decisions] == [
            "Bailey Bourque",
            "Carli VonWeinstein",
            "Quinn Absent",
            "Robin Example",
            "Sam Student",
        ]

    def test_count_by_status(self, use_case):
        request = DownselectConsentedStudentsRequest(
            entries=(
                ENTRY_CONSENTED,
                ENTRY_PARTIAL_NAME_MATCH,
                ENTRY_FALSE_BOOL,
                ENTRY_NAME_BLANK,
                ENTRY_NAME_MISMATCH,
            ),
            roster=(ROSTER_NO_RESPONSE,),
        )
        result = use_case.execute(request)
        assert result.count(ConsentStatus.INCLUDED) == 2
        assert result.count(ConsentStatus.DECLINED) == 1
        assert result.count(ConsentStatus.NAME_BLANK) == 1
        assert result.count(ConsentStatus.NAME_MISMATCH) == 1
        assert result.count(ConsentStatus.NO_RESPONSE) == 1

    def test_empty_inputs_have_no_decisions(self, use_case):
        result = use_case.execute(DownselectConsentedStudentsRequest(entries=()))
        assert result.decisions == ()


def status_for(use_case, lms_name: str, name_response: str) -> ConsentStatus:
    entry = ConsentFormEntry(
        canvas_id=200001,
        sis_id=5678901234,
        lms_name=lms_name,
        attempt=1,
        name_response=name_response,
        consented=True,
    )
    result = use_case.execute(DownselectConsentedStudentsRequest(entries=(entry,)))
    return only_decision(result).status


class TestNameMatching:
    @pytest.mark.parametrize(
        "name_response",
        ["Bourque Bailey", "Bourque, Bailey", "BAILEY BOURQUE"],
    )
    def test_swapped_or_recased_name_is_included(self, use_case, name_response):
        assert status_for(use_case, "Bailey Bourque", name_response) is ConsentStatus.INCLUDED

    @pytest.mark.parametrize(
        "name_response",
        [
            "Baily Bourqe",  # a letter missing from each name
            "Bialey Buorque",  # neighboring letters swapped
            "Bourqe, Baily",  # swapped order and a typo
            "Bayley Borque",  # one letter changed, one missing
        ],
    )
    def test_near_match_is_possible_typo(self, use_case, name_response):
        assert status_for(use_case, "Bailey Bourque", name_response) is ConsentStatus.POSSIBLE_TYPO

    def test_long_name_allows_two_typos(self, use_case):
        assert (
            status_for(use_case, "Carli Vonweinstein", "Karly Vonwienstien")
            is ConsentStatus.POSSIBLE_TYPO
        )

    def test_short_names_allow_no_typos(self, use_case):
        assert status_for(use_case, "Ana Li", "Ann Lu") is ConsentStatus.NAME_MISMATCH

    def test_more_than_a_couple_of_typos_is_mismatch(self, use_case):
        assert status_for(use_case, "Sam Bourque", "Pat Burke") is ConsentStatus.NAME_MISMATCH

    def test_possible_typo_is_excluded(self, use_case):
        entry = ConsentFormEntry(
            canvas_id=200001,
            sis_id=5678901234,
            lms_name="Bailey Bourque",
            attempt=1,
            name_response="Baily Bourqe",
            consented=True,
        )
        result = use_case.execute(DownselectConsentedStudentsRequest(entries=(entry,)))
        assert result.consented_ids == ()
        assert result.excluded_count == 1
