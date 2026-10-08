from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.consent_decision import ConsentStatus
from GAVEL.app.usecases.review_course_consent import (
    CONSENT_READ_ERRORS,
    ReviewCourseConsentRequest,
    ReviewCourseConsentResult,
    ReviewCourseConsentUseCase,
)
from tests.pages.sanitize.course_folders import EVERY_OUTCOME, build_course, write_students


def review(course: Path) -> ReviewCourseConsentResult:
    return ReviewCourseConsentUseCase().execute(ReviewCourseConsentRequest(course))


def test_missing_consent_form_is_reported_not_raised(tmp_path: Path):
    course = build_course(tmp_path, "ser222_26f_11111", consent_form=False)

    result = review(course)

    assert not result.consent_form_found
    assert result.decisions == ()


def test_every_student_gets_a_reason(tmp_path: Path):
    course = build_course(tmp_path, "ser222_26f_11111")
    write_students(course, EVERY_OUTCOME)

    statuses = {decision.name: decision.status for decision in review(course).decisions}

    assert statuses == {
        "Marisol Alvarez": ConsentStatus.INCLUDED,
        "Devon Brooks": ConsentStatus.INCLUDED,
        "Luca Esposito": ConsentStatus.NAME_BLANK,
        "Hannah Fischer": ConsentStatus.DECLINED,
        "Omar Haddad": ConsentStatus.NO_RESPONSE,
        "Kenji Ishikawa": ConsentStatus.POSSIBLE_TYPO,
        "Chinedu Okafor": ConsentStatus.NAME_MISMATCH,
    }


def test_included_count(tmp_path: Path):
    course = build_course(tmp_path, "ser222_26f_11111")
    write_students(course, EVERY_OUTCOME)

    assert review(course).included_count == 2


def test_without_a_roster_only_respondents_are_listed(tmp_path: Path):
    course = build_course(tmp_path, "ser222_26f_11111")
    write_students(course, EVERY_OUTCOME)
    (course / "original" / "roster.csv").unlink()

    names = [decision.name for decision in review(course).decisions]

    assert "Omar Haddad" not in names
    assert len(names) == len(EVERY_OUTCOME) - 1


def test_unreadable_consent_form_raises_a_read_error(tmp_path: Path):
    course = build_course(tmp_path, "ser222_26f_11111")
    (course / "original" / "consent_form.csv").write_text("nonsense\n", encoding="utf-8")

    with pytest.raises(CONSENT_READ_ERRORS):
        review(course)
