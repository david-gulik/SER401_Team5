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


def test_a_submission_with_no_tests_reads_as_having_an_empty_test_list(
    reader: YamlGradescopeReader, tmp_path: Path
) -> None:
    path = tmp_path / "no_tests.yml"
    path.write_text(
        "submission_1:\n"
        "  :created_at: 2026-01-01 00:00:00\n"
        "  :submitters:\n"
        "  - :sid: '1'\n"
        "    :email: student@example.com\n"
        "    :name: Test Student\n"
        "  :results:\n"
        "    output: The autograder could not run.\n"
    )
    [submission] = reader.read(path)
    assert submission.tests == []
