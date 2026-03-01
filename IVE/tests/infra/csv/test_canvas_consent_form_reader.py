"""Tests for CanvasConsentFormReader (infra/csv adapter)."""
from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from GAVEL.app.dtos.consent_form_entry import ConsentFormEntry
from GAVEL.infra.csv.canvas_consent_form_reader import CanvasConsentFormReader

EXPECTED_ROW_COUNT = 12
EXPECTED_CONSENTED_COUNT = 7
EXPECTED_NOT_CONSENTED_COUNT = 5


@pytest.fixture(scope="module")
def reader() -> CanvasConsentFormReader:
    return CanvasConsentFormReader()


@pytest.fixture(scope="module")
def entries(
    reader: CanvasConsentFormReader, consent_form_csv_path: Path
) -> List[ConsentFormEntry]:
    return list(reader.load(str(consent_form_csv_path)))


class TestCanvasConsentFormReader:

    def test_returns_all_rows(self, entries: List[ConsentFormEntry]) -> None:
        assert len(entries) == EXPECTED_ROW_COUNT

    def test_returns_consent_form_entry_instances(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        assert all(isinstance(e, ConsentFormEntry) for e in entries)

    def test_field_mapping_for_standard_consented_student(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        first = entries[0]
        assert first.sis_id == 309780
        assert first.lms_name == "Bourque, Bailey"
        assert first.attempt == 1
        assert first.name_response == "Bailey Bourque"
        assert first.consented is True

    def test_sis_id_is_parsed_as_int(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        assert all(isinstance(e.sis_id, int) for e in entries)

    def test_attempt_is_parsed_as_int(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        assert all(isinstance(e.attempt, int) for e in entries)

    def test_consented_is_bool(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        assert all(isinstance(e.consented, bool) for e in entries)

    def test_true_string_parses_to_true(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        consented = [e for e in entries if e.consented]
        assert len(consented) == EXPECTED_CONSENTED_COUNT

    def test_false_string_parses_to_false(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        # "Gulik, David" — explicit "False" in consent column
        gulik = next(e for e in entries if e.sis_id == 600001)
        assert gulik.consented is False

    def test_empty_consent_cell_parses_to_false(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        # "Nguyen, Kevin" — consent cell is blank (not "True" → False)
        nguyen = next(e for e in entries if e.sis_id == 600003)
        assert nguyen.consented is False

    def test_not_consented_count(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        not_consented = [e for e in entries if not e.consented]
        assert len(not_consented) == EXPECTED_NOT_CONSENTED_COUNT

    def test_blank_name_response_is_empty_string(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        # "Gulik, David" — left name field blank when declining
        gulik = next(e for e in entries if e.sis_id == 600001)
        assert gulik.name_response == ""

    def test_partial_name_response_preserved(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        # "Vonweinstein, Carli" — typed only first name
        carli = next(e for e in entries if e.sis_id == 771671)
        assert carli.name_response == "Carli"
        assert carli.consented is True

    def test_name_response_with_declined_consent(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        # "Reyes, Maria" — typed name but answered False
        reyes = next(e for e in entries if e.sis_id == 600002)
        assert reyes.name_response == "Maria Reyes"
        assert reyes.consented is False

    def test_mismatched_name_response_preserved(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        # "Patel, Riya" — typed a wrong name but consented True
        patel = next(e for e in entries if e.sis_id == 600004)
        assert patel.name_response == "wrongname"
        assert patel.consented is True

    def test_multiple_attempts_all_rows_present(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        # "Torres, James" submitted twice; both rows must be loaded
        torres = [e for e in entries if e.sis_id == 600005]
        assert len(torres) == 2
        assert {e.attempt for e in torres} == {1, 2}

    def test_multiple_attempts_consent_changes_between_attempts(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        # "Park, Soo" — declined on attempt 1, consented on attempt 2
        park = sorted(
            [e for e in entries if e.sis_id == 600006],
            key=lambda e: e.attempt,
        )
        assert park[0].consented is False  # attempt 1
        assert park[1].consented is True   # attempt 2

    def test_multiple_attempts_preserve_lms_name(
        self, entries: List[ConsentFormEntry]
    ) -> None:
        torres = [e for e in entries if e.sis_id == 600005]
        assert all(e.lms_name == "Torres, James" for e in torres)
