from __future__ import annotations

import pytest

from GAVEL.app.dtos.canvas_consent_form_entry import ConsentFormEntry
from GAVEL.app.usecases.anonymize_consent_form import (
    AnonymizeConsentFormRequest,
    AnonymizeConsentFormResult,
    AnonymizeConsentFormUseCase,
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

ENTRY_CONSENTED = ConsentFormEntry(
    sis_id=REAL_ID_CONSENTED,
    lms_name="Bailey Bourque",
    attempt=1,
    name_response="Bailey Bourque",
    consented=True,
)

ENTRY_NOT_CONSENTED = ConsentFormEntry(
    sis_id=REAL_ID_NOT_CONSENTED,
    lms_name="Lindy Crain",
    attempt=2,
    name_response="Lindy Crain",
    consented=False,
)

ENTRY_UNMAPPED = ConsentFormEntry(
    sis_id=REAL_ID_UNMAPPED,
    lms_name="Carli VonWeinstein",
    attempt=1,
    name_response="Carli",
    consented=True,
)


@pytest.fixture
def use_case() -> AnonymizeConsentFormUseCase:
    return AnonymizeConsentFormUseCase()


@pytest.fixture
def request_single_entry() -> AnonymizeConsentFormRequest:
    return AnonymizeConsentFormRequest(
        entries=(ENTRY_CONSENTED,),
        id_map=ID_MAP,
    )


class TestMappedEntryAnonymized:
    def test_returns_result(self, use_case, request_single_entry):
        result = use_case.execute(request_single_entry)
        assert isinstance(result, AnonymizeConsentFormResult)

    def test_entry_is_included(self, use_case, request_single_entry):
        result = use_case.execute(request_single_entry)
        assert len(result.entries) == 1

    def test_sis_id_is_anonymized(self, use_case, request_single_entry):
        result = use_case.execute(request_single_entry)
        assert result.entries[0].sis_id == ANON_ID_CONSENTED

    def test_lms_name_is_anonymized(self, use_case, request_single_entry):
        result = use_case.execute(request_single_entry)
        assert result.entries[0].lms_name == f"Anon{ANON_ID_CONSENTED} Anon"

    def test_name_response_is_blank(self, use_case, request_single_entry):
        result = use_case.execute(request_single_entry)
        assert result.entries[0].name_response == ""

    def test_attempt_is_preserved(self, use_case, request_single_entry):
        result = use_case.execute(request_single_entry)
        assert result.entries[0].attempt == ENTRY_CONSENTED.attempt

    def test_consented_is_preserved(self, use_case, request_single_entry):
        result = use_case.execute(request_single_entry)
        assert result.entries[0].consented == ENTRY_CONSENTED.consented

    def test_skipped_count_is_zero(self, use_case, request_single_entry):
        result = use_case.execute(request_single_entry)
        assert result.skipped_count == 0


class TestMultipleMappedEntries:
    def test_multiple_entries_are_anonymized(self, use_case):
        request = AnonymizeConsentFormRequest(
            entries=(ENTRY_CONSENTED, ENTRY_NOT_CONSENTED),
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.entries) == 2

    def test_false_consented_value_is_preserved(self, use_case):
        request = AnonymizeConsentFormRequest(
            entries=(ENTRY_NOT_CONSENTED,),
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.entries[0].consented is False


class TestUnmappedEntriesSkipped:
    def test_unmapped_entry_is_skipped(self, use_case):
        request = AnonymizeConsentFormRequest(
            entries=(ENTRY_UNMAPPED,),
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.entries == ()

    def test_skipped_count_incremented(self, use_case):
        request = AnonymizeConsentFormRequest(
            entries=(ENTRY_UNMAPPED,),
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.skipped_count == 1


class TestEmptyInputs:
    def test_empty_entries_returns_empty_result(self, use_case):
        request = AnonymizeConsentFormRequest(entries=(), id_map=ID_MAP)
        result = use_case.execute(request)
        assert result.entries == ()

    def test_empty_entries_zero_skipped(self, use_case):
        request = AnonymizeConsentFormRequest(entries=(), id_map=ID_MAP)
        result = use_case.execute(request)
        assert result.skipped_count == 0

    def test_empty_id_map_skips_all(self, use_case):
        request = AnonymizeConsentFormRequest(
            entries=(ENTRY_CONSENTED,),
            id_map=(),
        )
        result = use_case.execute(request)
        assert result.entries == ()
        assert result.skipped_count == 1


class TestOutputTypes:
    def test_result_entries_is_tuple(self, use_case, request_single_entry):
        result = use_case.execute(request_single_entry)
        assert isinstance(result.entries, tuple)

    def test_result_entries_are_consent_form_entries(self, use_case, request_single_entry):
        result = use_case.execute(request_single_entry)
        assert all(isinstance(entry, ConsentFormEntry) for entry in result.entries)
