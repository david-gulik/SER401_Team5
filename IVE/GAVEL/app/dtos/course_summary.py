from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from GAVEL.app.workspace.layout import CONSENT_FORM_FILE, CourseKey


class AnonymizationStatus(Enum):
    """Where a course folder stands with respect to its anonymized copy."""

    # original/consent_form.csv is missing, so nobody can be included
    NO_CONSENT_FORM = "no_consent_form"
    NOT_ANONYMIZED = "not_anonymized"
    # some input in original/ changed or appeared after it was anonymized
    OUT_OF_DATE = "out_of_date"
    UP_TO_DATE = "up_to_date"


class FileState(Enum):
    """One copy of a tracked file, in original/ or in anonymized/."""

    CURRENT = "current"
    OUT_OF_DATE = "out_of_date"
    MISSING = "missing"


@dataclass(frozen=True)
class TrackedFile:
    """A file the anonymizer reads from original/ and writes to anonymized/.

    path is relative to either folder, with "/" separators, so
    "assignments/7216983_m1/rubric_assessments.json" names both copies.
    The timestamps are file modification times; None means the copy is missing.
    """

    path: str
    original_at: datetime | None = None
    anonymized_at: datetime | None = None

    @property
    def original_state(self) -> FileState:
        return FileState.MISSING if self.original_at is None else FileState.CURRENT

    @property
    def anonymized_state(self) -> FileState:
        if self.anonymized_at is None:
            return FileState.MISSING
        # A copy whose original changed later, or is gone, no longer matches it.
        if self.original_at is None or self.original_at > self.anonymized_at:
            return FileState.OUT_OF_DATE
        return FileState.CURRENT

    @property
    def needs_anonymizing(self) -> bool:
        """The original exists but its anonymized copy is missing or stale."""
        return self.original_at is not None and self.anonymized_state is not FileState.CURRENT


@dataclass(frozen=True)
class ConsentTally:
    """How many students consent filtering keeps, out of every student it saw.

    total counts consent form respondents plus roster students who never
    responded.
    """

    included: int
    total: int


@dataclass(frozen=True)
class CourseSummary:
    """What a course folder holds, as far as anonymizing it is concerned."""

    key: CourseKey
    path: Path
    # Every file the anonymizer reads or writes, in display order.
    files: tuple[TrackedFile, ...] = ()
    # None when there is no consent form or it could not be read.
    consent: ConsentTally | None = None
    consent_unreadable: bool = False
    canvas_course_name: str | None = None

    @property
    def folder_name(self) -> str:
        return self.key.folder_name

    def file(self, path: str) -> TrackedFile | None:
        return next((f for f in self.files if f.path == path), None)

    @property
    def has_consent_form(self) -> bool:
        consent_form = self.file(CONSENT_FORM_FILE)
        return consent_form is not None and consent_form.original_at is not None

    @property
    def inputs_changed_at(self) -> datetime | None:
        """Newest modification time among the inputs in original/."""
        return max((f.original_at for f in self.files if f.original_at), default=None)

    @property
    def anonymized_at(self) -> datetime | None:
        """When anonymized/ was last written, or None if it holds none of the files."""
        return max((f.anonymized_at for f in self.files if f.anonymized_at), default=None)

    @property
    def status(self) -> AnonymizationStatus:
        if not self.has_consent_form:
            return AnonymizationStatus.NO_CONSENT_FORM
        if self.anonymized_at is None:
            return AnonymizationStatus.NOT_ANONYMIZED
        if any(
            f.needs_anonymizing or f.anonymized_state is FileState.OUT_OF_DATE for f in self.files
        ):
            return AnonymizationStatus.OUT_OF_DATE
        return AnonymizationStatus.UP_TO_DATE
