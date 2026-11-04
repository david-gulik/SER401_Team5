from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from GAVEL.app.dtos.consent_decision import ConsentStatus
from GAVEL.app.dtos.course_summary import AnonymizationStatus
from GAVEL.app.usecases.anonymize_course_dataset import (
    AnonymizeCourseDatasetRequest,
    build_anonymize_course_dataset_use_case,
)
from GAVEL.app.usecases.list_workspace_courses import (
    ListWorkspaceCoursesRequest,
    ListWorkspaceCoursesUseCase,
)
from GAVEL.app.usecases.override_consent import (
    ConsentOverrideError,
    OverrideConsentRequest,
    OverrideConsentUseCase,
)
from GAVEL.app.usecases.review_course_consent import (
    ReviewCourseConsentRequest,
    ReviewCourseConsentUseCase,
)
from GAVEL.app.workspace.manifest import load_manifest
from tests.pages.sanitize.course_folders import (
    EVERY_OUTCOME,
    build_course,
    change_original,
    sis_id,
    write_students,
)

# Indexes into EVERY_OUTCOME.
INCLUDED, BLANK, DECLINED, NO_RESPONSE, TYPO, MISMATCH = 0, 2, 3, 4, 5, 6


@pytest.fixture
def course(tmp_path: Path) -> Path:
    course = build_course(tmp_path, "ser222_26f_11111")
    write_students(course, EVERY_OUTCOME)
    return course


def override(course: Path, index: int, overridden: bool = True):
    return OverrideConsentUseCase().execute(
        OverrideConsentRequest(course, sis_id(index), overridden)
    )


def statuses(course: Path) -> dict[int, ConsentStatus]:
    review = ReviewCourseConsentUseCase().execute(ReviewCourseConsentRequest(course))
    return {decision.sis_id: decision.status for decision in review.decisions}


def manifest_json(course: Path) -> dict:
    return json.loads((course / "manifest.json").read_text(encoding="utf-8"))


def anonymize(course: Path) -> None:
    build_anonymize_course_dataset_use_case().execute(
        AnonymizeCourseDatasetRequest(snapshot_dir=course, seed=42, replace_existing=True)
    )


def anonymized_roster_size(course: Path) -> int:
    with (course / "anonymized" / "roster.csv").open(encoding="utf-8") as f:
        return len(list(csv.DictReader(f)))


def course_status(course: Path) -> AnonymizationStatus:
    (summary,) = (
        ListWorkspaceCoursesUseCase()
        .execute(ListWorkspaceCoursesRequest(course.parents[1]))
        .courses
    )
    return summary.status


class TestOverriding:
    @pytest.mark.parametrize("index", [TYPO, MISMATCH])
    def test_eligible_student_becomes_overridden(self, course, index):
        result = override(course, index)

        assert result.decision.status is ConsentStatus.OVERRIDDEN
        assert result.decision.included

    @pytest.mark.parametrize("index", [TYPO, MISMATCH])
    def test_override_is_saved_in_the_manifest_by_sis_id(self, course, index):
        override(course, index)

        entry = manifest_json(course)["consent_overrides"][str(sis_id(index))]
        assert entry["override"] is True
        assert entry["overridden_at"]

    @pytest.mark.parametrize("index", [INCLUDED, BLANK, DECLINED, NO_RESPONSE])
    def test_ineligible_student_is_refused(self, course, index):
        with pytest.raises(ConsentOverrideError, match="Only a possible typo or a name mismatch"):
            override(course, index)

        assert not (course / "manifest.json").exists()

    def test_unknown_student_is_refused(self, course):
        with pytest.raises(ConsentOverrideError, match="not on the consent form or roster"):
            OverrideConsentUseCase().execute(OverrideConsentRequest(course, 1))

    def test_folder_not_named_like_a_course_is_refused(self, tmp_path):
        folder = tmp_path / "loose"
        (folder / "original").mkdir(parents=True)

        with pytest.raises(ConsentOverrideError, match="not a course folder"):
            OverrideConsentUseCase().execute(OverrideConsentRequest(folder, sis_id(TYPO)))

    def test_removing_an_override_restores_the_original_result(self, course):
        override(course, TYPO)

        result = override(course, TYPO, overridden=False)

        assert result.decision.status is ConsentStatus.POSSIBLE_TYPO
        assert manifest_json(course)["consent_overrides"] == {}

    def test_removing_when_not_overridden_is_refused(self, course):
        with pytest.raises(ConsentOverrideError, match="is not overridden"):
            override(course, TYPO, overridden=False)


class TestLaterRuns:
    def test_override_applies_to_every_later_review(self, course):
        override(course, TYPO)
        override(course, MISMATCH)

        assert statuses(course)[sis_id(TYPO)] is ConsentStatus.OVERRIDDEN
        assert statuses(course)[sis_id(MISMATCH)] is ConsentStatus.OVERRIDDEN
        assert statuses(course)[sis_id(BLANK)] is ConsentStatus.NAME_BLANK

    def test_override_survives_a_fresh_download(self, course):
        override(course, TYPO)

        change_original(course, "consent_form.csv")

        assert statuses(course)[sis_id(TYPO)] is ConsentStatus.OVERRIDDEN

    def test_student_who_declines_later_is_left_out_despite_the_override(self, course):
        override(course, TYPO)
        students = list(EVERY_OUTCOME)
        name, typed, _, attempt = students[TYPO]
        students[TYPO] = (name, typed, False, attempt)

        write_students(course, tuple(students))

        assert statuses(course)[sis_id(TYPO)] is ConsentStatus.DECLINED


class TestAnonymizing:
    def test_overridden_student_is_anonymized(self, course):
        override(course, TYPO)

        anonymize(course)

        assert anonymized_roster_size(course) == 3  # two matching names plus the override

    def test_no_trace_of_the_override_in_anonymized_files(self, course):
        override(course, MISMATCH)
        name, typed, _, _ = EVERY_OUTCOME[MISMATCH]

        anonymize(course)

        # The student is in the output, under an anonymous ID.
        assert anonymized_roster_size(course) == 3
        written = [p for p in (course / "anonymized").rglob("*") if p.is_file()]
        for path in written:
            text = path.read_text(encoding="utf-8").lower()
            for needle in (str(sis_id(MISMATCH)), *name.lower().split(), typed.lower(), "overrid"):
                assert needle not in text, f"{needle!r} found in {path.name}"

    def test_run_records_the_overrides_it_used(self, course):
        override(course, TYPO)

        anonymize(course)

        anonymization = load_manifest(course / "manifest.json").anonymization
        assert anonymization.consent_overrides == (sis_id(TYPO),)

    def test_changing_an_override_marks_the_course_out_of_date(self, course):
        anonymize(course)
        assert course_status(course) is AnonymizationStatus.UP_TO_DATE

        override(course, TYPO)
        assert course_status(course) is AnonymizationStatus.OUT_OF_DATE

        anonymize(course)
        assert course_status(course) is AnonymizationStatus.UP_TO_DATE

        override(course, TYPO, overridden=False)
        assert course_status(course) is AnonymizationStatus.OUT_OF_DATE
