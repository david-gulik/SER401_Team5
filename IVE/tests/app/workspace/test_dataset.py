"""CourseDataset over the committed fixture course folder in tests/data/workspace.

The fixture was generated with the real layout, codec and recording code; the
integrity test below keeps it honest if someone edits a file by hand.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_gradebook import CanvasGradebook
from GAVEL.app.dtos.rubric_definition import RubricDefinition
from GAVEL.app.workspace.dataset import CourseDataset, DatasetReaders, MissingArtifactError
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.recording import sha256_of
from GAVEL.bootstrap import build_dataset_readers

FOLDER_NAME = "ser222_25sc_12345"
RUBRIC_ASSIGNMENT = 7216983
NO_RUBRIC_ASSIGNMENT = 7216972


@pytest.fixture(scope="module")
def readers() -> DatasetReaders:
    return build_dataset_readers()


@pytest.fixture(scope="module")
def folder(workspace_fixture_root: Path) -> CourseFolder:
    return Workspace(workspace_fixture_root).course(CourseKey.parse(FOLDER_NAME))


@pytest.fixture(scope="module")
def original(folder: CourseFolder, readers: DatasetReaders) -> CourseDataset:
    return CourseDataset.original(folder, readers)


@pytest.fixture(scope="module")
def anonymized(folder: CourseFolder, readers: DatasetReaders) -> CourseDataset:
    return CourseDataset.anonymized(folder, readers)


class TestFixtureIntegrity:
    def test_fixture_is_where_the_workspace_expects(self, workspace_fixture_root: Path) -> None:
        courses = Workspace(workspace_fixture_root).list_courses()
        assert [c.key.folder_name for c in courses] == [FOLDER_NAME]

    def test_every_manifest_artifact_matches_disk(self, original: CourseDataset) -> None:
        for entry in original.manifest.artifacts:
            path = original.folder.path / entry.path
            assert path.is_file(), entry.path
            assert sha256_of(path) == entry.sha256, entry.path
            assert path.stat().st_size == entry.size_bytes, entry.path

    def test_every_file_on_disk_is_in_the_manifest(self, original: CourseDataset) -> None:
        listed = {a.path for a in original.manifest.artifacts}
        on_disk = {
            p.relative_to(original.folder.path).as_posix()
            for p in original.folder.path.rglob("*")
            if p.is_file() and p.name != "manifest.json"
        }
        assert on_disk == listed


class TestManifest:
    def test_course_fields(self, original: CourseDataset) -> None:
        m = original.manifest
        assert m.key.folder_name == FOLDER_NAME
        assert m.canvas_course_id == 253450
        assert m.term_code == "2251"
        assert [mod.name for mod in m.modules] == ["Module 3: Lists", "Module 4: Analysis"]

    def test_assignments_come_from_manifest(self, original: CourseDataset) -> None:
        entries = original.assignments()
        assert [e.canvas_id for e in entries] == [NO_RUBRIC_ASSIGNMENT, RUBRIC_ASSIGNMENT]
        assert entries[1].module_number == 4
        assert entries[1].has_rubric is True
        assert entries[0].has_rubric is False

    def test_missing_manifest(self, tmp_path: Path, readers: DatasetReaders) -> None:
        folder = Workspace(tmp_path).course(CourseKey.parse(FOLDER_NAME))
        with pytest.raises(MissingArtifactError, match="manifest.json"):
            _ = CourseDataset.original(folder, readers).manifest


class TestCourseLevelFiles:
    def test_roster(self, original: CourseDataset, readers: DatasetReaders) -> None:
        students = original.roster()
        assert students == readers.roster.read(original.tree.roster_csv)
        assert len(students) > 0
        assert students[0].asurite

    def test_gradebook(self, original: CourseDataset) -> None:
        gradebook = original.gradebook()
        assert isinstance(gradebook, CanvasGradebook)
        assert len(gradebook.rows) == 3
        assert {c.canvas_id for c in gradebook.columns} >= {RUBRIC_ASSIGNMENT, NO_RUBRIC_ASSIGNMENT}

    def test_consent_form(self, original: CourseDataset, readers: DatasetReaders) -> None:
        entries = original.consent_form()
        assert list(entries) == list(readers.consent_form.read(str(original.tree.consent_form_csv)))
        assert len(entries) > 0

    def test_quiz_csv_missing(self, original: CourseDataset) -> None:
        with pytest.raises(MissingArtifactError, match="quiz 99"):
            original.quiz_csv(99)

    def test_missing_file_names_the_tree(self, anonymized: CourseDataset) -> None:
        with pytest.raises(MissingArtifactError) as excinfo:
            anonymized.gradebook()
        assert "anonymized" in str(excinfo.value)
        assert isinstance(excinfo.value, FileNotFoundError)


class TestAssignments:
    def test_rubric_definition(self, original: CourseDataset) -> None:
        definition = original.rubric_definition(RUBRIC_ASSIGNMENT)
        assert isinstance(definition, RubricDefinition)
        assert definition.title == "Problem Set Rubric"
        assert [c.description for c in definition.criteria] == ["Correctness", "Clarity"]

    def test_rubric_assessments(self, original: CourseDataset) -> None:
        assessments = original.rubric_assessments(RUBRIC_ASSIGNMENT)
        assert [a.student_id for a in assessments] == [100001, 100002]
        assert assessments[0].criteria[0].points == 4.0

    def test_assignment_without_rubric_gives_none(self, original: CourseDataset) -> None:
        assert original.rubric_definition(NO_RUBRIC_ASSIGNMENT) is None
        assert original.rubric_assessments(NO_RUBRIC_ASSIGNMENT) == ()

    def test_lookup_ignores_module_tag(self, original: CourseDataset) -> None:
        assert original.assignment_folder(RUBRIC_ASSIGNMENT).name == "7216983_m4"

    def test_unknown_assignment(self, original: CourseDataset) -> None:
        with pytest.raises(MissingArtifactError, match="assignment 1"):
            original.rubric_assessments(1)

    def test_gradescope_submissions_missing(self, original: CourseDataset) -> None:
        with pytest.raises(MissingArtifactError, match="Gradescope"):
            original.gradescope_submissions(RUBRIC_ASSIGNMENT)


class TestGradescopeZip:
    """Built in tmp_path: a Gradescope export is a zip with submission_metadata.yml inside."""

    @pytest.fixture
    def dataset(self, tmp_path: Path, readers: DatasetReaders, data_dir: Path) -> CourseDataset:
        folder = Workspace(tmp_path).course(CourseKey.parse(FOLDER_NAME))
        assignment = folder.original.assignment(RUBRIC_ASSIGNMENT, 4)
        assignment.path.mkdir(parents=True)
        with zipfile.ZipFile(assignment.submissions_zip, "w") as archive:
            archive.write(data_dir / "submission_metadata.yml", "export/submission_metadata.yml")
            archive.writestr("export/submission_1/Main.java", "class Main {}")
        return CourseDataset.original(folder, readers)

    def test_reads_metadata_from_zip(self, dataset: CourseDataset) -> None:
        submissions = dataset.gradescope_submissions(RUBRIC_ASSIGNMENT)
        assert len(submissions) > 0
        assert submissions[0].submitter.sid

    def test_zip_without_metadata(self, dataset: CourseDataset) -> None:
        zip_path = dataset.assignment_folder(RUBRIC_ASSIGNMENT).submissions_zip
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("readme.txt", "empty export")
        with pytest.raises(MissingArtifactError, match="submission_metadata.yml"):
            dataset.gradescope_submissions(RUBRIC_ASSIGNMENT)


class TestAnonymizedTree:
    def test_same_code_reads_the_other_tree(self, anonymized: CourseDataset) -> None:
        students = anonymized.roster()
        assert [s.asurite for s in students] == ["aanon1", "aanon2"]
        assert anonymized.tree.root.name == "anonymized"

    def test_manifest_is_shared(self, original: CourseDataset, anonymized: CourseDataset) -> None:
        assert anonymized.manifest == original.manifest
        assert anonymized.manifest.artifact("anonymized/roster.csv") is not None
