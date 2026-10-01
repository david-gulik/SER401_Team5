from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

DATA_DIR = Path(__file__).parent / "data"
TOKENS_PATH = Path(__file__).parents[1] / "GAVEL" / "theme" / "tokens_dark.json"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def roster_csv_path(data_dir: Path) -> Path:
    return data_dir / "test_roster.csv"


@pytest.fixture(scope="session")
def consent_form_csv_path(data_dir: Path) -> Path:
    return data_dir / "test_consentform.csv"


@pytest.fixture(scope="session")
def gradebook_csv_path(data_dir: Path) -> Path:
    return data_dir / "test_gradebook.csv"


@pytest.fixture(scope="session")
def qapp():
    """One offscreen QApplication for the whole session (widgets require it)."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="session")
def theme():
    from GAVEL.theme.context import ThemeContext
    from GAVEL.theme.tokens import load_tokens

    return ThemeContext(tokens=load_tokens(TOKENS_PATH))
