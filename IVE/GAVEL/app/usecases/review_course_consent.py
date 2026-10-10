from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.consent_decision import ConsentDecision
from GAVEL.app.usecases.downselect_consented_students import (
    DownselectConsentedStudentsRequest,
    DownselectConsentedStudentsUseCase,
)
from GAVEL.app.workspace.layout import ORIGINAL_DIR, DataTree
from GAVEL.infra.csv.canvas_consent_form_csv_reader import CanvasConsentFormCSVReader
from GAVEL.infra.csv.canvas_roster_csv_reader import CanvasRosterCSVReader

# What a malformed consent form or roster raises from the CSV readers.
CONSENT_READ_ERRORS = (OSError, ValueError, KeyError)


@dataclass(frozen=True)
class ReviewCourseConsentRequest:
    course_dir: Path


@dataclass(frozen=True)
class ReviewCourseConsentResult:
    # False when original/consent_form.csv does not exist; decisions is then empty.
    consent_form_found: bool
    # One per student, sorted by name, with roster-only students as NO_RESPONSE.
    decisions: tuple[ConsentDecision, ...] = ()

    @property
    def included_count(self) -> int:
        return sum(1 for decision in self.decisions if decision.included)


class ReviewCourseConsentUseCase:
    """Who in a course folder consent filtering keeps, and why the rest are left out.

    Applies the same filtering the anonymizer does, without writing anything.
    A consent form or roster that cannot be parsed raises one of
    CONSENT_READ_ERRORS.
    """

    def __init__(
        self,
        consent_form_reader: CanvasConsentFormCSVReader | None = None,
        roster_reader: CanvasRosterCSVReader | None = None,
        downselect_use_case: DownselectConsentedStudentsUseCase | None = None,
    ) -> None:
        self._consent_form_reader = consent_form_reader or CanvasConsentFormCSVReader()
        self._roster_reader = roster_reader or CanvasRosterCSVReader()
        self._downselect_use_case = downselect_use_case or DownselectConsentedStudentsUseCase()

    def execute(self, request: ReviewCourseConsentRequest) -> ReviewCourseConsentResult:
        original = DataTree(request.course_dir / ORIGINAL_DIR)
        if not original.consent_form_csv.is_file():
            return ReviewCourseConsentResult(consent_form_found=False)

        entries = tuple(self._consent_form_reader.read(str(original.consent_form_csv)))
        roster = (
            tuple(self._roster_reader.read(original.roster_csv))
            if original.roster_csv.is_file()
            else ()
        )
        result = self._downselect_use_case.execute(
            DownselectConsentedStudentsRequest(entries=entries, roster=roster)
        )
        return ReviewCourseConsentResult(consent_form_found=True, decisions=result.decisions)
