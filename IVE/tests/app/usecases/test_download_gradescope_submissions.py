"""DownloadGradescopeSubmissionsUseCase with a fake scraper that drops zips in the staging folder."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.canvas_course import CanvasAssignment
from GAVEL.app.usecases.download_gradescope_submissions import (
    DownloadGradescopeSubmissionsRequest,
    DownloadGradescopeSubmissionsUseCase,
    match_gradescope_name,
    normalise_name,
)
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import load_manifest
from GAVEL.app.workspace.recording import ArtifactExistsError
from tests.pages.download.fakes import FakeCanvasClient

COURSE_ID = 253450
ASSIGNMENTS = [
    CanvasAssignment(id=7216972, name="Module 3: Programming (Gradescope)"),
    CanvasAssignment(id=7216983, name="Module 4: ADJ Problem Set"),
    CanvasAssignment(id=7216990, name="Final Exam", has_rubric=False),
]


class FakeScraper:
    """Stands in for http_gradescope_client: writes canned zips into submissions_folder."""

    created: list[FakeScraper] = []

    def __init__(self, exports: dict[str, bytes]) -> None:
        self.exports = exports
        self.kwargs: dict = {}
        self.downloads = 0

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self

    def download_all_assignments(self, username: str, password: str) -> None:
        self.downloads += 1
        folder = Path(self.kwargs["submissions_folder"])
        for name, content in self.exports.items():
            (folder / f"{name}.zip").write_bytes(content)


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


class TestRelocation:
    def test_files_land_under_the_matching_assignment(self, canvas, folder):
        scraper = FakeScraper(
            {
                "Module 4 ADJ Problem Set": b"subs4",
                "Module 4 ADJ Problem Set_autograder": b"ag4",
                "Module 3 Programming": b"subs3",
            }
        )
        result = make_use_case(canvas, scraper).execute(
            DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder)
        )

        m4 = folder.original.assignment(7216983, 4)
        m3 = folder.original.assignment(7216972, 3)
        assert m4.submissions_zip.read_bytes() == b"subs4"
        assert m4.autograder_zip.read_bytes() == b"ag4"
        assert m3.submissions_zip.read_bytes() == b"subs3"
        assert not m3.autograder_zip.exists()
        assert result.saved_path == folder.original.assignments_dir
        assert len(result.matched) == 3 and result.unmatched == ()
        assert "3 matched" in result.message

    def test_scraper_is_pointed_at_the_staging_folder_which_is_removed_after(self, canvas, folder):
        scraper = FakeScraper({"Module 3 Programming": b"x"})
        make_use_case(canvas, scraper).execute(
            DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder, headless=True)
        )
        staging = Path(scraper.kwargs["submissions_folder"])
        assert staging == folder.original.assignments_dir / "_staging"
        assert scraper.kwargs["headless"] is True
        assert str(COURSE_ID) in scraper.kwargs["course_url"]
        assert not staging.exists()

    def test_unmatched_export_is_kept_and_recorded(self, canvas, folder):
        scraper = FakeScraper({"Mystery Assignment": b"???"})
        result = make_use_case(canvas, scraper).execute(
            DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder)
        )
        kept = folder.original.assignments_dir / "_unmatched" / "Mystery Assignment.zip"
        assert kept.read_bytes() == b"???"
        assert [a.gradescope_name for a in result.unmatched] == ["Mystery Assignment"]
        assert "Mystery Assignment" in result.message
        entry = load_manifest(folder.manifest_path).artifact(
            "original/assignments/_unmatched/Mystery Assignment.zip"
        )
        assert entry is not None
        assert entry.kind == "submissions" and entry.source_id is None
        assert entry.label == "Mystery Assignment"

    def test_manifest_records_matched_artifacts_and_assignments(self, canvas, folder):
        scraper = FakeScraper(
            {"Module 4 ADJ Problem Set": b"s", "Module 4 ADJ Problem Set_autograder": b"a"}
        )
        make_use_case(canvas, scraper).execute(
            DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder)
        )
        manifest = load_manifest(folder.manifest_path)
        subs = manifest.artifact("original/assignments/7216983_m4/submissions.zip")
        ag = manifest.artifact("original/assignments/7216983_m4/autograder.zip")
        assert subs is not None and subs.kind == "submissions" and subs.source_id == 7216983
        assert ag is not None and ag.kind == "autograder" and ag.source_id == 7216983
        entry = manifest.assignment(7216983)
        assert entry is not None
        assert entry.gradescope_name == "Module 4 ADJ Problem Set"
        assert entry.module_number == 4
        assert manifest.canvas_course_id == COURSE_ID

    def test_reuses_an_existing_assignment_folder(self, canvas, folder):
        folder.original.assignment(7216983, 7).path.mkdir(parents=True)
        scraper = FakeScraper({"Module 4 ADJ Problem Set": b"s"})
        make_use_case(canvas, scraper).execute(
            DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder)
        )
        assert folder.original.assignment(7216983, 7).submissions_zip.exists()

    def test_unreachable_assignment_list_leaves_everything_unmatched(self, folder):
        class NoList(FakeCanvasClient):
            def list_assignments(self, course_id: int) -> list[CanvasAssignment]:
                raise RuntimeError("Canvas not configured")

        scraper = FakeScraper({"Module 4 ADJ Problem Set": b"s"})
        result = make_use_case(NoList(), scraper).execute(
            DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder)
        )
        assert len(result.unmatched) == 1


class TestGuard:
    def test_missing_credentials_stop_before_the_browser(self, canvas, folder):
        scraper = FakeScraper({})
        with pytest.raises(RuntimeError, match="CANVAS_USERNAME"):
            make_use_case(canvas, scraper, creds=(None, None)).execute(
                DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder)
            )
        assert scraper.downloads == 0

    def test_second_download_is_refused_before_the_browser(self, canvas, folder):
        scraper = FakeScraper({"Module 4 ADJ Problem Set": b"s"})
        request = DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder)
        make_use_case(canvas, scraper).execute(request)
        with pytest.raises(ArtifactExistsError, match="submissions.zip"):
            make_use_case(canvas, scraper).execute(request)
        assert scraper.downloads == 1

    def test_overwrite_downloads_again(self, canvas, folder):
        scraper = FakeScraper({"Module 4 ADJ Problem Set": b"first"})
        request = DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder)
        make_use_case(canvas, scraper).execute(request)
        scraper.exports = {"Module 4 ADJ Problem Set": b"second"}
        make_use_case(canvas, scraper).execute(
            DownloadGradescopeSubmissionsRequest(course_id=COURSE_ID, folder=folder, overwrite=True)
        )
        assert folder.original.assignment(7216983, 4).submissions_zip.read_bytes() == b"second"

    def test_invalid_course_id(self, canvas, folder):
        with pytest.raises(ValueError):
            make_use_case(canvas, FakeScraper({})).execute(
                DownloadGradescopeSubmissionsRequest(course_id=0, folder=folder)
            )
