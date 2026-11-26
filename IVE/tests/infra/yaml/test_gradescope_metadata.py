from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from GAVEL.infra.yaml.gradescope_metadata import load_gradescope_metadata

SUBMISSION_1 = (
    "submission_1:\n"
    "  :created_at: 2026-01-01 00:00:00\n"
    "  :submitters:\n"
    "  - :sid: '1'\n"
    "    :email: one@example.com\n"
    "    :name: Student One\n"
)
SUBMISSION_2 = (
    "submission_2:\n"
    "  :created_at: 2026-01-01 00:00:00\n"
    "  :submitters:\n"
    "  - :sid: '2'\n"
    "    :email: two@example.com\n"
    "    :name: Student Two\n"
)


def load(tmp_path: Path, text: str) -> dict:
    path = tmp_path / "submission_metadata.yml"
    path.write_text(text, encoding="utf-8")
    return load_gradescope_metadata(path)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(SUBMISSION_1 + SUBMISSION_2, id="plain"),
        # What Gradescope sent for SER 222 m5: PyYAML alone stops at the "...".
        pytest.param(SUBMISSION_1 + "...\n" + SUBMISSION_2, id="document end between"),
        pytest.param(SUBMISSION_1 + "...   \n" + SUBMISSION_2, id="document end, trailing spaces"),
        pytest.param(SUBMISSION_1 + "...\n---\n" + SUBMISSION_2, id="document end then start"),
        pytest.param("---\n" + SUBMISSION_1 + "---\n" + SUBMISSION_2, id="document starts only"),
        pytest.param(SUBMISSION_1 + SUBMISSION_2 + "...\n", id="document end last"),
        pytest.param(SUBMISSION_1 + SUBMISSION_2 + "...", id="document end, no final newline"),
    ],
)
def test_every_submission_is_read_whatever_document_markers_surround_them(
    tmp_path: Path, text: str
) -> None:
    assert list(load(tmp_path, text)) == ["submission_1", "submission_2"]


def test_crlf_line_endings_are_handled(tmp_path: Path) -> None:
    path = tmp_path / "submission_metadata.yml"
    path.write_bytes((SUBMISSION_1 + "...\n" + SUBMISSION_2).replace("\n", "\r\n").encode())

    assert list(load_gradescope_metadata(path)) == ["submission_1", "submission_2"]


def test_an_ellipsis_inside_autograder_output_is_kept(tmp_path: Path) -> None:
    text = (
        SUBMISSION_1
        + "  :results:\n"
        + "    output: |\n"
        + "      Compiling\n"
        + "      ...\n"
        + "      Done\n"
        + "...\n"
        + SUBMISSION_2
    )

    data = load(tmp_path, text)

    assert data["submission_1"][":results"]["output"] == "Compiling\n...\nDone\n"
    assert "submission_2" in data


@pytest.mark.parametrize("text", ["", "---\n", "...\n"])
def test_a_file_with_no_submissions_reads_as_empty(tmp_path: Path, text: str) -> None:
    assert load(tmp_path, text) == {}


def test_a_file_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(yaml.YAMLError):
        load(tmp_path, "- submission_1\n- submission_2\n")


def test_malformed_yaml_is_still_rejected(tmp_path: Path) -> None:
    with pytest.raises(yaml.YAMLError):
        load(tmp_path, "submission_1: [unclosed\n")
