from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.consent_decision import ConsentDecision, ConsentStatus
from GAVEL.app.usecases.review_course_consent import (
    ReviewCourseConsentRequest,
    ReviewCourseConsentUseCase,
)
from GAVEL.app.workspace.layout import CourseFolder, CourseKey
from GAVEL.app.workspace.recording import note_consent_override


class ConsentOverrideError(ValueError):
    """The student cannot be overridden, or their override cannot be removed."""


@dataclass(frozen=True)
class OverrideConsentRequest:
    course_dir: Path
    sis_id: int
    # False removes an earlier override.
    overridden: bool = True


@dataclass(frozen=True)
class OverrideConsentResult:
    # The student's decision once the change is saved.
    decision: ConsentDecision


class OverrideConsentUseCase:
    """Include a student whose typed name did not match, or undo that.

    Only a POSSIBLE_TYPO or NAME_MISMATCH student can be overridden. The
    override is saved in the course manifest, keyed by SIS ID, where later
    reviews and anonymization runs pick it up. The student's current decision
    is read fresh from the course folder, so a stale table cannot override
    someone who has since declined.
    """

    def __init__(self, review_consent: ReviewCourseConsentUseCase | None = None) -> None:
        self._review_consent = review_consent or ReviewCourseConsentUseCase()

    def execute(self, request: OverrideConsentRequest) -> OverrideConsentResult:
        try:
            key = CourseKey.parse(request.course_dir.name)
        except ValueError as exc:
            raise ConsentOverrideError(
                f"{request.course_dir} is not a course folder, so it has no manifest to "
                "save overrides in"
            ) from exc
        folder = CourseFolder(request.course_dir, key)

        decision = self._decision(request)
        if request.overridden and not decision.overridable:
            raise ConsentOverrideError(
                f"{decision.name} ({decision.sis_id}) is {_describe(decision.status)}. Only a "
                "possible typo or a name mismatch can be overridden."
            )
        if not request.overridden and decision.status is not ConsentStatus.OVERRIDDEN:
            raise ConsentOverrideError(f"{decision.name} ({decision.sis_id}) is not overridden.")

        note_consent_override(folder, request.sis_id, request.overridden)
        return OverrideConsentResult(decision=self._decision(request))

    def _decision(self, request: OverrideConsentRequest) -> ConsentDecision:
        review = self._review_consent.execute(ReviewCourseConsentRequest(request.course_dir))
        decision = next((d for d in review.decisions if d.sis_id == request.sis_id), None)
        if decision is None:
            raise ConsentOverrideError(
                f"SIS ID {request.sis_id} is not on the consent form or roster."
            )
        return decision


def _describe(status: ConsentStatus) -> str:
    return status.value.replace("_", " ")
