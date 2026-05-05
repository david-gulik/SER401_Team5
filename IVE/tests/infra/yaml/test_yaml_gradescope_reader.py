from __future__ import annotations

from pathlib import Path

import pytest

from GAVEL.app.dtos.gradescope import GradescopeSubmission
from GAVEL.infra.yaml.yaml_gradescope_reader import YamlGradescopeReader


@pytest.fixture(scope="module")
def reader() -> YamlGradescopeReader:
    return YamlGradescopeReader()


@pytest.fixture(scope="module")
def submissions(reader: YamlGradescopeReader, data_dir: Path) -> list[GradescopeSubmission]:
    return reader.read(data_dir / "submission_metadata.yml")


class TestYamlGradescopeReader:
    def test_returns_submissions(self, submissions: list[GradescopeSubmission]) -> None:
        assert len(submissions) > 0

    def test_submission_has_submitter(self, submissions: list[GradescopeSubmission]) -> None:
        first = submissions[0]
        assert first.submitter.sid != ""

    def test_submission_has_tests(self, submissions: list[GradescopeSubmission]) -> None:
        first = submissions[0]
        assert len(first.tests) > 0
