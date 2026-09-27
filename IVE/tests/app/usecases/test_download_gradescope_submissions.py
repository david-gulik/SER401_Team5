"""DownloadGradescopeSubmissionsUseCase with a fake scraper that drops zips in the staging folder."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.usecases.download_gradescope_submissions import (
    DownloadGradescopeSubmissionsRequest,
    DownloadGradescopeSubmissionsUseCase,
    match_gradescope_name,
    module_for_export,
    normalise_name,
)
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import load_manifest
from GAVEL.app.workspace.recording import ArtifactExistsError, artifact_path
from tests.pages.download.fakes import FakeCanvasClient

COURSE_ID = 253450
ASSIGNMENTS = [
    CanvasAssignment(id=7216972, name="Module 3: Programming (Gradescope)"),
    CanvasAssignment(id=7216983, name="Module 4: ADJ Problem Set"),
    CanvasAssignment(id=7216990, name="Final Exam", has_rubric=False),
    CanvasAssignment(id=7217000, name="Cairn", has_rubric=True),  # no module in the name
]


def export_zip(*names: str) -> bytes:
    """A Gradescope-style bulk export: metadata yml plus one folder per submission."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("submission_metadata.yml", "---\n")
        for name in names:
            archive.writestr(f"{name}/Main.java", "class Main {}")
    return buffer.getvalue()


class FakeScraper:
    """Stands in for http_gradescope_client: writes canned zips into submissions_folder."""

    def __init__(self, exports: dict[str, bytes]) -> None:
        self.exports = exports
        self.kwargs: dict = {}
        self.downloads = 0

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self

    def download_all_assignments(self, username: str, password: str) -> list[str]:
        self.downloads += 1
        folder = Path(self.kwargs["submissions_folder"])
        written = []
        for name, content in self.exports.items():
            path = folder / f"{name}.zip"
            path.write_bytes(content)
            written.append(str(path))
        return written


@pytest.fixture
def folder(tmp_path: Path) -> CourseFolder:
    return Workspace(tmp_path).course(CourseKey.parse("ser222_25sc_12345"))


@pytest.fixture
def canvas() -> FakeCanvasClient:
    return FakeCanvasClient(assignments=ASSIGNMENTS)


def make_use_case(canvas, scraper: FakeScraper, creds=("user", "pw")):
    return DownloadGradescopeSubmissionsUseCase(
        canvas, client_factory=scraper, credentials=lambda: creds
    )


def run(canvas, folder, scraper: FakeScraper, **kwargs):
    return make_use_case(canvas, scraper).execute(
        DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder, **kwargs)
    )


class TestNameMatching:
    def test_normalise(self) -> None:
        assert normalise_name("  Module 3:  Programming? ") == "module 3 programming"

    @pytest.mark.parametrize(
        ("gradescope_name", "expected_id"),
        [
            ("Module 4: ADJ Problem Set", 7216983),
            ("Module 4 ADJ Problem Set", 7216983),  # scraper strips the colon
            ("module 4: adj problem set", 7216983),
            ("Module 3: Programming", 7216972),  # Canvas name carries "(Gradescope)"
            ("Module 3 Programming (Gradescope)", 7216972),
            ("Module 3: Programming (Gradescope) v2", 7216972),  # prefix, one candidate
            ("Module 9: Nothing", None),
            ("Module", None),  # prefix of several
            ("", None),
        ],
    )
    def test_match(self, gradescope_name: str, expected_id: int | None) -> None:
        match = match_gradescope_name(gradescope_name, ASSIGNMENTS)
        assert (None if match is None else match.id) == expected_id

    @pytest.mark.parametrize(
        ("gradescope_name", "module", "assignment_id"),
        [
            ("Module 2 Programming", 2, None),  # module from the name, no Canvas twin
            ("Module 3 Programming", 3, 7216972),
            ("Mod 7 Something", 7, None),
            ("Cairn", None, 7217000),  # matched, but neither name says which module
            ("Practice Exam", None, None),
        ],
    )
    def test_module_for_export(self, gradescope_name, module, assignment_id) -> None:
        got_module, got_assignment = module_for_export(gradescope_name, ASSIGNMENTS)
        assert got_module == module
        assert (None if got_assignment is None else got_assignment.id) == assignment_id


class TestFiling:
    def test_exports_are_grouped_by_module(self, canvas, folder):
        result = run(
            canvas,
            folder,
            FakeScraper(
                {
                    "Module 2 Programming": export_zip("alice_1", "bob_2"),
                    "Module 3 Programming": export_zip("carol_3"),
                }
            ),
        )

        m2 = folder.original.module_submissions(2)
        m3 = folder.original.module_submissions(3)
        assert zipfile.is_zipfile(m2.zip_path) and zipfile.is_zipfile(m3.zip_path)
        assert result.saved_path == folder.original.submissions_dir
        assert sorted(a.module_number for a in result.matched) == [2, 3]
        assert result.unmatched == ()
        assert "filed under module(s) m2, m3" in result.message

    def test_submissions_are_extracted_next_to_the_zip(self, canvas, folder):
        run(canvas, folder, FakeScraper({"Module 2 Programming": export_zip("alice_1", "bob_2")}))
        extracted = folder.original.module_submissions(2).extracted_dir
        assert (extracted / "submission_metadata.yml").exists()
        assert (extracted / "alice_1" / "Main.java").read_text() == "class Main {}"
        assert (extracted / "bob_2" / "Main.java").exists()

    def test_autograder_goes_to_the_workspace_autograders_area(self, canvas, folder, tmp_path):
        result = run(
            canvas,
            folder,
            FakeScraper(
                {
                    "Module 2 Programming": export_zip("alice_1"),
                    "Module 2 Programming_autograder": b"GRADER",
                }
            ),
        )
        snapshot = (
            tmp_path / "autograders" / "ser222" / "m2" / "ser222_25sc_12345" / "autograder.zip"
        )
        assert snapshot.read_bytes() == b"GRADER"
        assert not (folder.path / "autograders").exists()
        grader = next(a for a in result.artifacts if a.kind == "autograder")
        assert grader.saved_path == snapshot and grader.module_number == 2

    def test_manifest_records_everything_with_the_right_bases(self, canvas, folder):
        run(
            canvas,
            folder,
            FakeScraper(
                {
                    "Module 3 Programming": export_zip("alice_1"),
                    "Module 3 Programming_autograder": b"GRADER",
                }
            ),
        )
        manifest = load_manifest(folder.manifest_path)
        subs = manifest.artifact("original/submissions/m3/submissions.zip")
        grader = manifest.artifact("autograders/ser222/m3/ser222_25sc_12345/autograder.zip")
        assert subs is not None and subs.kind == "submissions"
        assert subs.source_id == 7216972 and subs.label == "Module 3 Programming"
        assert grader is not None and grader.kind == "autograder"
        assert artifact_path(folder, grader).exists()
        entry = manifest.assignment(7216972)
        assert entry is not None and entry.module_number == 3
        assert entry.gradescope_name == "Module 3 Programming"
        assert manifest.canvas_course_id == COURSE_ID
        # the extracted copy is derived from the zip and is not an artifact of its own
        assert all("extracted" not in a.path for a in manifest.artifacts)

    def test_module_from_the_canvas_twin_when_the_gradescope_name_has_none(self, canvas, folder):
        canvas.assignments.append(CanvasAssignment(id=7218000, name="Module 5: Hash Tables"))
        result = run(canvas, folder, FakeScraper({"Hash Tables": export_zip("x")}))
        assert [a.module_number for a in result.matched] == [5]
        assert folder.original.module_submissions(5).zip_path.exists()

    def test_export_without_a_module_is_kept_and_recorded(self, canvas, folder):
        result = run(canvas, folder, FakeScraper({"Practice Exam": b"???"}))
        kept = folder.original.submissions_dir / "_unmatched" / "Practice Exam.zip"
        assert kept.read_bytes() == b"???"
        assert [a.gradescope_name for a in result.unmatched] == ["Practice Exam"]
        assert "Practice Exam" in result.message
        entry = load_manifest(folder.manifest_path).artifact(
            "original/submissions/_unmatched/Practice Exam.zip"
        )
        assert entry is not None
        assert entry.kind == "submissions" and entry.source_id is None
        assert entry.label == "Practice Exam"

    def test_scraper_is_pointed_at_the_staging_folder_which_is_removed_after(self, canvas, folder):
        scraper = FakeScraper({"Module 3 Programming": export_zip("x")})
        run(canvas, folder, scraper, headless=True)
        staging = Path(scraper.kwargs["submissions_folder"])
        assert staging == folder.original.submissions_dir / "_staging"
        assert scraper.kwargs["headless"] is True
        assert str(COURSE_ID) in scraper.kwargs["course_url"]
        assert not staging.exists()

    def test_unreachable_assignment_list_still_files_by_module(self, folder):
        class NoList(FakeCanvasClient):
            def list_assignments(self, course_id: int) -> list[CanvasAssignment]:
                raise RuntimeError("Canvas not configured")

        result = run(
            NoList(),
            folder,
            FakeScraper({"Module 4 ADJ Problem Set": export_zip("x"), "Cairn": b"?"}),
        )
        assert [a.module_number for a in result.matched] == [4]
        assert [a.gradescope_name for a in result.unmatched] == ["Cairn"]
        assert "Canvas assignment list could not be fetched" in result.message


class TestGuard:
    def test_missing_credentials_stop_before_the_browser(self, canvas, folder):
        scraper = FakeScraper({})
        with pytest.raises(RuntimeError, match="CANVAS_USERNAME"):
            make_use_case(canvas, scraper, creds=(None, None)).execute(
                DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder)
            )
        assert scraper.downloads == 0

    def test_second_download_is_refused_before_the_browser(self, canvas, folder):
        scraper = FakeScraper({"Module 2 Programming": export_zip("x")})
        run(canvas, folder, scraper)
        with pytest.raises(ArtifactExistsError, match="submissions.zip"):
            run(canvas, folder, scraper)
        assert scraper.downloads == 1

    def test_overwrite_downloads_again_and_replaces_the_extraction(self, canvas, folder):
        scraper = FakeScraper({"Module 2 Programming": export_zip("alice_1")})
        run(canvas, folder, scraper)
        scraper.exports = {"Module 2 Programming": export_zip("bob_2")}
        run(canvas, folder, scraper, overwrite=True)
        extracted = folder.original.module_submissions(2).extracted_dir
        assert (extracted / "bob_2").exists()
        assert not (extracted / "alice_1").exists()

    def test_invalid_course_id(self, canvas, folder):
        with pytest.raises(ValueError):
            make_use_case(canvas, FakeScraper({})).execute(
                DownloadGradescopeSubmissionsRequest(course_id=0, folder=folder)
            )
