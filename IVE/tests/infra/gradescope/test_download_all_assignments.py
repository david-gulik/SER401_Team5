"""The scraper writes one zip per export into the folder it is given, and nowhere else."""

from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.infra.gradescope.http_gradescope_client import GradescopeSession, http_gradescope_client

GS_COURSE = "999"
BASE = "https://www.gradescope.com"

ASSIGNMENTS_HTML = f"""
<div data-assignment-id="11" aria-describedby="course-{GS_COURSE}">Module 3: Programming</div>
<div data-assignment-id="12" aria-describedby="course-{GS_COURSE}">Module 4: ADJ Problem Set</div>
"""
AUTOGRADER_HTML = f'<a href="{BASE}/files/autograder_ser222_m3.zip?x=1">Download Autograder</a>'
NO_AUTOGRADER_HTML = "<html><body>no autograder</body></html>"
EXPORT_READY_HTML = '<a class="js-bulkExportModalDownload" href="/exports/11/download.zip">zip</a>'
EXPORT_MISSING_HTML = '<meta name="csrf-token" content="csrf123"><div>nothing exported yet</div>'


class FakeResponse:
    def __init__(self, text: str = "", content: bytes = b"", payload: dict | None = None):
        self.text = text
        self.content = content
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class FakeSession:
    """Answers the URLs the scraper visits for two assignments: one exported, one not."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.gets: list[str] = []
        self.posts: list[str] = []
        self.polls = 0

    def get(self, url: str) -> FakeResponse:
        self.gets.append(url)
        if url.endswith(f"/courses/{GS_COURSE}/assignments"):
            return FakeResponse(text=ASSIGNMENTS_HTML)
        if url.endswith("/assignments/11/configure_autograder"):
            return FakeResponse(text=AUTOGRADER_HTML)
        if url.endswith("/assignments/12/configure_autograder"):
            return FakeResponse(text=NO_AUTOGRADER_HTML)
        if url.endswith("/assignments/11/review_grades"):
            return FakeResponse(text=EXPORT_READY_HTML)
        if url.endswith("/assignments/12/review_grades"):
            return FakeResponse(text=EXPORT_MISSING_HTML)
        if "autograder_ser222_m3.zip" in url:
            return FakeResponse(content=b"AUTOGRADER")
        if url.endswith("/exports/11/download.zip"):
            return FakeResponse(content=b"SUBS-11")
        if url.endswith("/generated_files/77.json"):
            self.polls += 1
            return FakeResponse(payload={"progress": 1.0 if self.polls > 1 else 0.5})
        if url.endswith("/generated_files/77.zip"):
            return FakeResponse(content=b"SUBS-12")
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url: str, headers: dict | None = None) -> FakeResponse:
        self.posts.append(url)
        assert url.endswith("/assignments/12/export")
        assert self.headers["X-CSRF-Token"] == "csrf123"
        return FakeResponse(payload={"generated_file_id": 77})


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> tuple[http_gradescope_client, FakeSession, Path]:
    folder = tmp_path / "staging"
    client = http_gradescope_client(
        "https://canvas.asu.edu/courses/123456", submissions_folder=str(folder)
    )
    session = FakeSession()
    monkeypatch.setattr(
        client, "capture_session", lambda u, p: (GradescopeSession("c", "t", {}), GS_COURSE)
    )
    monkeypatch.setattr(client, "_build_requests_session", lambda gs, course_id: session)
    monkeypatch.setattr("GAVEL.infra.gradescope.http_gradescope_client.time.sleep", lambda s: None)
    return client, session, folder


def test_every_export_lands_in_submissions_folder(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # any hard-coded relative path would show up here
    scraper, session, folder = client

    written = scraper.download_all_assignments(username="u", password="p")

    assert sorted(p.name for p in folder.iterdir()) == [
        "Module 3 Programming.zip",
        "Module 3 Programming_autograder.zip",
        "Module 4 ADJ Problem Set.zip",
    ]
    assert (folder / "Module 3 Programming.zip").read_bytes() == b"SUBS-11"
    assert (folder / "Module 3 Programming_autograder.zip").read_bytes() == b"AUTOGRADER"
    assert (folder / "Module 4 ADJ Problem Set.zip").read_bytes() == b"SUBS-12"
    assert sorted(Path(w).name for w in written) == sorted(p.name for p in folder.iterdir())
    assert not (tmp_path / "GAVEL").exists()


def test_missing_export_is_triggered_and_polled(client):
    scraper, session, _ = client
    scraper.download_all_assignments(username="u", password="p")
    assert session.posts == [f"{BASE}/courses/{GS_COURSE}/assignments/12/export"]
    assert session.polls == 2


def test_zip_is_kept_as_is_not_extracted(client):
    scraper, _, folder = client
    scraper.download_all_assignments(username="u", password="p")
    assert [p for p in folder.iterdir() if p.is_dir()] == []


def test_folder_is_created_when_missing(client):
    scraper, _, folder = client
    assert not folder.exists()
    scraper.download_all_assignments(username="u", password="p")
    assert folder.is_dir()
