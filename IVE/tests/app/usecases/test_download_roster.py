from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.roster import RosterRequest
from GAVEL.app.usecases.download_roster import DownloadRosterRequest, DownloadRosterUseCase
from GAVEL.app.workspace.layout import CourseFolder, CourseKey, Workspace
from GAVEL.app.workspace.manifest import load_manifest
from GAVEL.app.workspace.recording import ArtifactExistsError
from tests.pages.download.fakes import FakeRosterClient

TERM = "2251"
CLASS_NUMBER = "12345"


@pytest.fixture
def client() -> FakeRosterClient:
    return FakeRosterClient(roster_csv="Student,ID\r\nAda Lovelace,1000000001\r\n")


@pytest.fixture
def folder(tmp_path: Path) -> CourseFolder:
    return Workspace(tmp_path).course(CourseKey.parse("ser222_25sc_12345"))


@pytest.fixture
def request_(folder: CourseFolder) -> DownloadRosterRequest:
    return DownloadRosterRequest(term=TERM, class_number=CLASS_NUMBER, folder=folder)


class TestHappyPath:
    def test_writes_roster_csv_with_normalised_newlines(self, client, request_, folder):
        result = DownloadRosterUseCase(client).execute(request_)
        assert result.saved_path == folder.original.roster_csv
        assert folder.original.roster_csv.read_bytes() == b"Student,ID\nAda Lovelace,1000000001\n"

    def test_fetches_the_requested_class(self, client, request_):
        DownloadRosterUseCase(client).execute(request_)
        assert client.roster_requests == [RosterRequest(term=TERM, class_number=CLASS_NUMBER)]

    def test_authenticates_once_and_closes(self, client, request_):
        DownloadRosterUseCase(client).execute(request_)
        assert client.authenticate_calls == 1
        assert client.close_calls == 1

    def test_closes_even_when_the_fetch_fails(self, request_):
        class Failing(FakeRosterClient):
            def fetch_roster(self, request: RosterRequest) -> str:
                raise RuntimeError("myASU down")

        client = Failing()
        with pytest.raises(RuntimeError, match="myASU down"):
            DownloadRosterUseCase(client).execute(request_)
        assert client.close_calls == 1

    def test_manifest_records_file_and_term(self, client, request_, folder):
        DownloadRosterUseCase(client).execute(request_)
        manifest = load_manifest(folder.manifest_path)
        entry = manifest.artifact("original/roster.csv")
        assert entry is not None and entry.kind == "roster"
        assert manifest.term_code == TERM

    def test_message_names_the_course(self, client, request_):
        result = DownloadRosterUseCase(client).execute(request_)
        assert "SER 222" in result.message
        assert CLASS_NUMBER in result.message


class TestGuard:
    def test_second_download_is_refused_before_authenticating(self, client, request_):
        DownloadRosterUseCase(client).execute(request_)
        with pytest.raises(ArtifactExistsError):
            DownloadRosterUseCase(client).execute(request_)
        assert client.authenticate_calls == 1

    def test_overwrite_downloads_again(self, client, request_, folder):
        DownloadRosterUseCase(client).execute(request_)
        client.roster_csv = "Student,ID\nGrace Hopper,2\n"
        DownloadRosterUseCase(client).execute(
            DownloadRosterRequest(
                term=TERM, class_number=CLASS_NUMBER, folder=folder, overwrite=True
            )
        )
        assert folder.original.roster_csv.read_text(encoding="utf-8").startswith(
            "Student,ID\nGrace"
        )


class TestValidation:
    @pytest.mark.parametrize(("term", "class_number"), [("", "12345"), ("2251", ""), (" ", " ")])
    def test_blank_inputs_rejected(self, client, folder, term, class_number):
        with pytest.raises(ValueError):
            DownloadRosterUseCase(client).execute(
                DownloadRosterRequest(term=term, class_number=class_number, folder=folder)
            )
        assert client.authenticate_calls == 0
