from __future__ import annotations

from pathlib import Path

from GAVEL.app.workspace.layout import default_workspace_root


def test_follows_default_output_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DEFAULT_OUTPUT_DIR", str(tmp_path))

    assert default_workspace_root() == tmp_path


def test_falls_back_to_the_downloads_folder(monkeypatch):
    monkeypatch.delenv("DEFAULT_OUTPUT_DIR", raising=False)

    assert default_workspace_root() == Path.home() / "Downloads" / "GAVEL"


def test_a_blank_default_output_dir_counts_as_unset(monkeypatch):
    monkeypatch.setenv("DEFAULT_OUTPUT_DIR", "   ")

    assert default_workspace_root() == Path.home() / "Downloads" / "GAVEL"
