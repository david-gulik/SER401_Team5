from __future__ import annotations

import pytest

from GAVEL.app.dtos.asu_roster import RosterStudent
from GAVEL.app.usecases.anonymize_roster import (
    AnonymizeRosterRequest,
    AnonymizeRosterResult,
    AnonymizeRosterUseCase,
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

STUDENT_CONSENTED = RosterStudent(
    id=str(REAL_ID_CONSENTED),
    posting_id=f"{REAL_ID_CONSENTED}-000",
    first_name="Bailey",
    last_name="Bourque",
    status="Active",
    units=3,
    grade_basis="Graded",
    program_and_plan="Unknown",
    academic_level="Undergraduate",
    asurite="brbourqu",
    residency="Resident",
    zoom_email="brbourqu@asu.edu",
)

STUDENT_NOT_CONSENTED = RosterStudent(
    id=str(REAL_ID_NOT_CONSENTED),
    posting_id=f"{REAL_ID_NOT_CONSENTED}-000",
    first_name="Lindy",
    last_name="Crain",
    status="Active",
    units=3,
    grade_basis="Graded",
    program_and_plan="Unknown",
    academic_level="Undergraduate",
    asurite="lcrain",
    residency="Resident",
    zoom_email="lcrain@asu.edu",
)

STUDENT_UNMAPPED = RosterStudent(
    id=str(REAL_ID_UNMAPPED),
    posting_id=f"{REAL_ID_UNMAPPED}-000",
    first_name="Carli",
    last_name="VonWeinstein",
    status="Active",
    units=3,
    grade_basis="Graded",
    program_and_plan="Unknown",
    academic_level="Undergraduate",
    asurite="cvonwein",
    residency="Resident",
    zoom_email="cvonwein@asu.edu",
)


@pytest.fixture
def use_case() -> AnonymizeRosterUseCase:
    return AnonymizeRosterUseCase()


@pytest.fixture
def request_single_consented() -> AnonymizeRosterRequest:
    return AnonymizeRosterRequest(
        students=(STUDENT_CONSENTED,),
        consented_ids=CONSENTED_IDS,
        id_map=ID_MAP,
    )


class TestConsentedStudentIncluded:
    def test_returns_result(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert isinstance(result, AnonymizeRosterResult)

    def test_consented_student_is_included(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert len(result.students) == 1

    def test_id_is_replaced_with_anonymous_id(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.students[0].id == str(ANON_ID_CONSENTED)

    def test_posting_id_is_replaced(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.students[0].posting_id == f"{ANON_ID_CONSENTED}-000"

    def test_first_name_is_anonymized(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.students[0].first_name == "Anon"

    def test_last_name_is_anonymized(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.students[0].last_name == f"Anon{ANON_ID_CONSENTED}"

    def test_asurite_is_anonymized(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.students[0].asurite == f"aanon{ANON_ID_CONSENTED}"

    def test_zoom_email_is_anonymized(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.students[0].zoom_email == f"aanon{ANON_ID_CONSENTED}@anon.com"

    def test_non_pii_fields_are_preserved(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        student = result.students[0]
        assert student.status == STUDENT_CONSENTED.status
        assert student.units == STUDENT_CONSENTED.units
        assert student.grade_basis == STUDENT_CONSENTED.grade_basis
        assert student.program_and_plan == STUDENT_CONSENTED.program_and_plan
        assert student.academic_level == STUDENT_CONSENTED.academic_level
        assert student.residency == STUDENT_CONSENTED.residency

    def test_skipped_count_is_zero(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.skipped_count == 0

    def test_excluded_count_is_zero(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.excluded_count == 0


class TestNonConsentedStudentExcluded:
    def test_non_consented_student_is_excluded(self, use_case):
        request = AnonymizeRosterRequest(
            students=(STUDENT_NOT_CONSENTED,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.students) == 0

    def test_excluded_count_incremented(self, use_case):
        request = AnonymizeRosterRequest(
            students=(STUDENT_NOT_CONSENTED,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.excluded_count == 1

    def test_only_consented_retained_when_mixed(self, use_case):
        request = AnonymizeRosterRequest(
            students=(STUDENT_CONSENTED, STUDENT_NOT_CONSENTED),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.students) == 1
        assert result.students[0].id == str(ANON_ID_CONSENTED)

    def test_excluded_count_correct_when_mixed(self, use_case):
        request = AnonymizeRosterRequest(
            students=(STUDENT_CONSENTED, STUDENT_NOT_CONSENTED),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.excluded_count == 1


class TestUnmappedStudentSkipped:
    def test_unmapped_student_is_skipped(self, use_case):
        request = AnonymizeRosterRequest(
            students=(STUDENT_UNMAPPED,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.students) == 0

    def test_skipped_count_incremented(self, use_case):
        request = AnonymizeRosterRequest(
            students=(STUDENT_UNMAPPED,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.skipped_count == 1

    def test_skipped_does_not_raise(self, use_case):
        request = AnonymizeRosterRequest(
            students=(STUDENT_UNMAPPED,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result is not None


class TestEmptyInputs:
    def test_empty_students_returns_empty_result(self, use_case):
        request = AnonymizeRosterRequest(
            students=(),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.students == ()

    def test_empty_students_zero_counts(self, use_case):
        request = AnonymizeRosterRequest(
            students=(),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.skipped_count == 0
        assert result.excluded_count == 0

    def test_empty_consented_ids_excludes_all(self, use_case):
        request = AnonymizeRosterRequest(
            students=(STUDENT_CONSENTED,),
            consented_ids=(),
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.students) == 0

    def test_empty_id_map_skips_all(self, use_case):
        request = AnonymizeRosterRequest(
            students=(STUDENT_CONSENTED,),
            consented_ids=CONSENTED_IDS,
            id_map=(),
        )
        result = use_case.execute(request)
        assert len(result.students) == 0


class TestSortedOutput:
    def test_output_is_sorted_by_anonymized_last_name(self, use_case):
        request = AnonymizeRosterRequest(
            students=(STUDENT_NOT_CONSENTED, STUDENT_CONSENTED),
            consented_ids=(REAL_ID_CONSENTED, REAL_ID_NOT_CONSENTED),
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert [student.last_name for student in result.students] == [
            f"Anon{ANON_ID_CONSENTED}",
            f"Anon{ANON_ID_NOT_CONSENTED}",
        ]


class TestOutputTypes:
    def test_result_students_is_tuple(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert isinstance(result.students, tuple)

    def test_result_entries_are_roster_students(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert all(isinstance(student, RosterStudent) for student in result.students)