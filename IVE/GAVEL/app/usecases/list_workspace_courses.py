from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from GAVEL.app.dtos.course_summary import ConsentTally, CourseSummary, TrackedFile
from GAVEL.app.usecases.review_course_consent import (
    CONSENT_READ_ERRORS,
    ReviewCourseConsentRequest,
    ReviewCourseConsentUseCase,
)
from GAVEL.app.workspace.layout import (
    ASSIGNMENTS_DIR,
    CONSENT_FORM_FILE,
    GRADEBOOK_FILE,
    ORIGINAL_DIR,
    ROSTER_FILE,
    RUBRIC_ASSESSMENTS_FILE,
    CourseFolder,
    Workspace,
)
from GAVEL.app.workspace.manifest import (
    AnonymizationEntry,
    CourseManifest,
    ManifestError,
    load_manifest,
)
from GAVEL.app.workspace.recording import sha256_of

# The files the anonymizer reads from original/ and writes to anonymized/,
# besides one rubric_assessments.json per assignment folder.
_TOP_LEVEL_FILES = (CONSENT_FORM_FILE, ROSTER_FILE, GRADEBOOK_FILE)


@dataclass(frozen=True)
class ListWorkspaceCoursesRequest:
    workspace_root: Path


@dataclass(frozen=True)
class ListWorkspaceCoursesResult:
    # Sorted by folder name. Folders under courses/ whose names do not parse
    # as a course are left out.
    courses: tuple[CourseSummary, ...]


class ListWorkspaceCoursesUseCase:
    """Summarize every course folder in a workspace. Reads only; writes nothing."""

    def __init__(self, review_consent: ReviewCourseConsentUseCase | None = None) -> None:
        self._review_consent = review_consent or ReviewCourseConsentUseCase()

    def execute(self, request: ListWorkspaceCoursesRequest) -> ListWorkspaceCoursesResult:
        folders = Workspace(request.workspace_root).list_courses()
        return ListWorkspaceCoursesResult(
            courses=tuple(self._summarize(folder) for folder in folders),
        )

    def _summarize(self, folder: CourseFolder) -> CourseSummary:
        consent, unreadable = self._tally_consent(folder)
        manifest = _manifest(folder)
        return CourseSummary(
            key=folder.key,
            path=folder.path,
            files=_tracked_files(folder, manifest.anonymization if manifest else None),
            consent=consent,
            consent_unreadable=unreadable,
            canvas_course_name=manifest.canvas_course_name if manifest else None,
        )

    def _tally_consent(self, folder: CourseFolder) -> tuple[ConsentTally | None, bool]:
        """``(tally, unreadable)``: the same filtering the anonymizer applies."""
        try:
            review = self._review_consent.execute(ReviewCourseConsentRequest(folder.path))
        except CONSENT_READ_ERRORS:
            # One bad CSV should not keep the other courses from listing.
            return None, True
        if not review.consent_form_found:
            return None, False
        return ConsentTally(included=review.included_count, total=len(review.decisions)), False


def _tracked_files(
    folder: CourseFolder, anonymization: AnonymizationEntry | None
) -> tuple[TrackedFile, ...]:
    original, anonymized = folder.original, folder.anonymized
    rubric_paths = sorted(
        {
            f"{ASSIGNMENTS_DIR}/{assignment.name}/{RUBRIC_ASSESSMENTS_FILE}"
            for tree in (original, anonymized)
            for assignment in tree.list_assignments()
            if assignment.rubric_assessments_json.is_file()
        }
    )
    return tuple(
        _tracked_file(original.root / path, anonymized.root / path, path, anonymization)
        for path in (*_TOP_LEVEL_FILES, *rubric_paths)
    )


def _tracked_file(
    original: Path, anonymized: Path, path: str, anonymization: AnonymizationEntry | None
) -> TrackedFile:
    original_at = _modified_at(original)
    anonymized_at = _modified_at(anonymized)
    recorded = anonymization.source(f"{ORIGINAL_DIR}/{path}") if anonymization else None
    # Hashing is only worth it when there is a copy and a record to compare with.
    compare = recorded is not None and original_at is not None and anonymized_at is not None
    return TrackedFile(
        path=path,
        original_at=original_at,
        anonymized_at=anonymized_at,
        original_sha256=sha256_of(original) if compare else None,
        anonymized_from_sha256=recorded.sha256 if recorded else None,
    )


def _modified_at(path: Path) -> datetime | None:
    return datetime.fromtimestamp(path.stat().st_mtime) if path.is_file() else None


def _manifest(folder: CourseFolder) -> CourseManifest | None:
    # A missing or unreadable manifest costs the label and makes every
    # anonymized copy read as out of date, but keeps the course listed.
    if not folder.manifest_path.is_file():
        return None
    try:
        return load_manifest(folder.manifest_path)
    except (ManifestError, OSError):
        return None
