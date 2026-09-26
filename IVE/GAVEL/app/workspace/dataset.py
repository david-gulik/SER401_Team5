"""Read one course folder back into the DTOs the rest of GAVEL already uses.

``CourseDataset`` is a thin facade: it knows where each file is (from
``DataTree``) and which reader port parses it (from ``DatasetReaders``).
The same class reads ``original/`` and ``anonymized/`` because both trees
have the same shape.

Typical use::

    folder = Workspace(root).course(CourseKey.parse("ser222_25sc_12345"))
    data = CourseDataset.original(folder, services.dataset_readers)
    roster = data.roster()
    for entry in data.assignments():
        scores = data.rubric_assessments(entry.canvas_id)
"""

from __future__ import annotations

import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from GAVEL.app.dtos.asu_roster import RosterStudent
from GAVEL.app.dtos.canvas_consent_form_entry import ConsentFormEntry
from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.gradescope import GradescopeSubmission
from GAVEL.app.dtos.rubric_assessment import RubricAssessment
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.app.ports.asu_roster_reader import RosterReader
from GAVEL.app.ports.canvas_consent_form_reader import ConsentFormReader
from GAVEL.app.ports.canvas_gradebook_reader import GradebookReader
from GAVEL.app.ports.gradescope_reader import GradescopeReader
from GAVEL.app.ports.rubric_assessment_reader import RubricAssessmentReader
from GAVEL.app.ports.rubric_definition_reader import RubricDefinitionReader
from GAVEL.app.workspace.layout import AssignmentFolder, CourseFolder, DataTree
from GAVEL.app.workspace.manifest import AssignmentEntry, CourseManifest, load_manifest

GRADESCOPE_METADATA_FILE = "submission_metadata.yml"


@dataclass(frozen=True)
class DatasetReaders:
    """The reader port for each file type"""

    roster: RosterReader
    gradebook: GradebookReader
    consent_form: ConsentFormReader
    rubric_definition: RubricDefinitionReader
    rubric_assessments: RubricAssessmentReader
    gradescope: GradescopeReader


class MissingArtifactError(FileNotFoundError):
    """A file the caller asked for was never downloaded into this tree."""

    def __init__(self, tree: DataTree, what: str, path: Path) -> None:
        self.tree = tree
        self.path = path
        super().__init__(f"{what} has not been downloaded into {tree.root} (expected {path})")


class CourseDataset:
    def __init__(self, folder: CourseFolder, tree: DataTree, readers: DatasetReaders) -> None:
        self._folder = folder
        self._tree = tree
        self._readers = readers
        self._manifest: CourseManifest | None = None

    @classmethod
    def original(cls, folder: CourseFolder, readers: DatasetReaders) -> CourseDataset:
        return cls(folder, folder.original, readers)

    @classmethod
    def anonymized(cls, folder: CourseFolder, readers: DatasetReaders) -> CourseDataset:
        return cls(folder, folder.anonymized, readers)

    @property
    def folder(self) -> CourseFolder:
        return self._folder

    @property
    def tree(self) -> DataTree:
        return self._tree

    @property
    def manifest(self) -> CourseManifest:
        if self._manifest is None:
            path = self._folder.manifest_path
            if not path.exists():
                raise MissingArtifactError(self._tree, "manifest.json", path)
            self._manifest = load_manifest(path)
        return self._manifest

    def roster(self) -> list[RosterStudent]:
        return self._readers.roster.read(self._require("roster", self._tree.roster_csv))

    def gradebook(self) -> CanvasGradebook:
        return self._readers.gradebook.read(
            str(self._require("gradebook", self._tree.gradebook_csv))
        )

    def consent_form(self) -> Sequence[ConsentFormEntry]:
        return self._readers.consent_form.read(
            str(self._require("consent form", self._tree.consent_form_csv))
        )

    def quiz_csv(self, quiz_id: int) -> Path:
        """Path to a quiz student-analysis export. No DTO exists for it yet."""
        return self._require(f"quiz {quiz_id}", self._tree.quiz_csv(quiz_id))

    def assignments(self) -> tuple[AssignmentEntry, ...]:
        """Assignments as recorded in the manifest, in Canvas id order."""
        return self.manifest.assignments

    def assignment_folder(self, assignment_id: int) -> AssignmentFolder:
        folder = self._tree.find_assignment(assignment_id)
        if folder is None:
            raise MissingArtifactError(
                self._tree,
                f"assignment {assignment_id}",
                self._tree.assignment(assignment_id).path,
            )
        return folder

    def rubric_definition(self, assignment_id: int) -> RubricDefinition | None:
        """The rubric attached to an assignment, or None when it has none."""
        path = self.assignment_folder(assignment_id).rubric_definition_json
        if not path.exists():
            return None
        return self._readers.rubric_definition.read(path)

    def rubric_assessments(self, assignment_id: int) -> tuple[RubricAssessment, ...]:
        path = self.assignment_folder(assignment_id).rubric_assessments_json
        return self._readers.rubric_assessments.read(
            self._require(f"rubric assessments for assignment {assignment_id}", path)
        )

    def gradescope_submissions(self, assignment_id: int) -> list[GradescopeSubmission]:
        """Submissions from the Gradescope export zip's ``submission_metadata.yml``."""
        zip_path = self._require(
            f"Gradescope submissions for assignment {assignment_id}",
            self.assignment_folder(assignment_id).submissions_zip,
        )
        with zipfile.ZipFile(zip_path) as archive:
            member = next(
                (n for n in archive.namelist() if n.split("/")[-1] == GRADESCOPE_METADATA_FILE),
                None,
            )
            if member is None:
                raise MissingArtifactError(
                    self._tree, f"{GRADESCOPE_METADATA_FILE} inside {zip_path.name}", zip_path
                )
            with tempfile.TemporaryDirectory() as tmp:
                extracted = Path(tmp) / GRADESCOPE_METADATA_FILE
                extracted.write_bytes(archive.read(member))
                return self._readers.gradescope.read(extracted)

    def _require(self, what: str, path: Path) -> Path:
        if not path.exists():
            raise MissingArtifactError(self._tree, what, path)
        return path
