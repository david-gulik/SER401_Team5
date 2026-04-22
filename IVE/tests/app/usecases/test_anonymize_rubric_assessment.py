"""
Unit tests for AnonymizeRubricAssessmentUseCase.
"""

from __future__ import annotations

import pytest

from GAVEL.app.dtos.rubric_assessment import RubricAssessment, RubricCriterionScore
from GAVEL.app.usecases.anonymize_rubric_assessment import (
    AnonymizeRubricAssessmentRequest,
    AnonymizeRubricAssessmentResult,
    AnonymizeRubricAssessmentUseCase,
)

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

REAL_ID_CONSENTED = 1217482318
REAL_ID_NOT_CONSENTED = 9999999999
REAL_ID_UNMAPPED = 1111111111

ANON_ID_CONSENTED = 4242

ID_MAP = ((REAL_ID_CONSENTED, ANON_ID_CONSENTED), (REAL_ID_NOT_CONSENTED, 5555))
CONSENTED_IDS = (REAL_ID_CONSENTED,)

CRITERION = RubricCriterionScore(
    criterion_id="340525_8699",
    points=2.0,
    comments="Q2 Justification: Alignment comment.",
)

ASSESSMENT_CONSENTED = RubricAssessment(
    student_id=REAL_ID_CONSENTED,
    submission_id=9001,
    criteria=(CRITERION,),
)

ASSESSMENT_NOT_CONSENTED = RubricAssessment(
    student_id=REAL_ID_NOT_CONSENTED,
    submission_id=9002,
    criteria=(CRITERION,),
)

ASSESSMENT_UNMAPPED = RubricAssessment(
    student_id=REAL_ID_UNMAPPED,
    submission_id=9003,
    criteria=(CRITERION,),
)

ASSESSMENT_NO_CRITERIA = RubricAssessment(
    student_id=REAL_ID_CONSENTED,
    submission_id=9004,
    criteria=(),
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def use_case() -> AnonymizeRubricAssessmentUseCase:
    return AnonymizeRubricAssessmentUseCase()


@pytest.fixture
def request_single_consented() -> AnonymizeRubricAssessmentRequest:
    return AnonymizeRubricAssessmentRequest(
        assessments=(ASSESSMENT_CONSENTED,),
        consented_ids=CONSENTED_IDS,
        id_map=ID_MAP,
    )


# ---------------------------------------------------------------------------
# Happy path — consented student included and anonymized
# ---------------------------------------------------------------------------


class TestConsentedStudentIncluded:
    def test_returns_result(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert isinstance(result, AnonymizeRubricAssessmentResult)

    def test_consented_student_is_included(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert len(result.assessments) == 1

    def test_student_id_is_replaced_with_anonymous_id(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.assessments[0].student_id == ANON_ID_CONSENTED

    def test_real_student_id_is_not_present(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.assessments[0].student_id != REAL_ID_CONSENTED

    def test_submission_id_is_replaced_with_synthetic_id(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.assessments[0].submission_id == int("30000" + str(ANON_ID_CONSENTED))

    def test_real_submission_id_is_not_present(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.assessments[0].submission_id != ASSESSMENT_CONSENTED.submission_id

    def test_criteria_are_preserved_unchanged(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.assessments[0].criteria == (CRITERION,)

    def test_criterion_points_preserved(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.assessments[0].criteria[0].points == CRITERION.points

    def test_criterion_comments_preserved(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.assessments[0].criteria[0].comments == CRITERION.comments

    def test_criterion_id_preserved(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.assessments[0].criteria[0].criterion_id == CRITERION.criterion_id

    def test_skipped_count_is_zero(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.skipped_count == 0

    def test_excluded_count_is_zero(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert result.excluded_count == 0


# ---------------------------------------------------------------------------
# Non-consented student excluded
# ---------------------------------------------------------------------------


class TestNonConsentedStudentExcluded:
    def test_non_consented_student_is_excluded(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_NOT_CONSENTED,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.assessments) == 0

    def test_excluded_count_incremented(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_NOT_CONSENTED,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.excluded_count == 1

    def test_only_consented_retained_when_mixed(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_CONSENTED, ASSESSMENT_NOT_CONSENTED),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.assessments) == 1
        assert result.assessments[0].student_id == ANON_ID_CONSENTED

    def test_excluded_count_correct_when_mixed(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_CONSENTED, ASSESSMENT_NOT_CONSENTED),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.excluded_count == 1


# ---------------------------------------------------------------------------
# Unmapped student ID skipped
# ---------------------------------------------------------------------------


class TestUnmappedStudentSkipped:
    def test_unmapped_student_is_skipped(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_UNMAPPED,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.assessments) == 0

    def test_skipped_count_incremented(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_UNMAPPED,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.skipped_count == 1

    def test_skipped_does_not_raise(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_UNMAPPED,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result is not None


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------


class TestEmptyInputs:
    def test_empty_assessments_returns_empty_result(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.assessments == ()

    def test_empty_assessments_zero_counts(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.skipped_count == 0
        assert result.excluded_count == 0

    def test_empty_consented_ids_excludes_all(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_CONSENTED,),
            consented_ids=(),
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.assessments) == 0

    def test_empty_id_map_skips_all(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_CONSENTED,),
            consented_ids=CONSENTED_IDS,
            id_map=(),
        )
        result = use_case.execute(request)
        assert len(result.assessments) == 0


# ---------------------------------------------------------------------------
# Assessment with no criteria
# ---------------------------------------------------------------------------


class TestNoCriteria:
    def test_assessment_with_no_criteria_is_included(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_NO_CRITERIA,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert len(result.assessments) == 1

    def test_empty_criteria_preserved(self, use_case):
        request = AnonymizeRubricAssessmentRequest(
            assessments=(ASSESSMENT_NO_CRITERIA,),
            consented_ids=CONSENTED_IDS,
            id_map=ID_MAP,
        )
        result = use_case.execute(request)
        assert result.assessments[0].criteria == ()


# ---------------------------------------------------------------------------
# Output is a valid tuple of RubricAssessment
# ---------------------------------------------------------------------------


class TestOutputTypes:
    def test_result_assessments_is_tuple(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert isinstance(result.assessments, tuple)

    def test_result_entries_are_rubric_assessments(self, use_case, request_single_consented):
        result = use_case.execute(request_single_consented)
        assert all(isinstance(a, RubricAssessment) for a in result.assessments)
