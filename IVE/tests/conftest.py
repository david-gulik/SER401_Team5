from __future__ import annotations

from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def roster_csv_path(data_dir: Path) -> Path:
    return data_dir / "ser222_00sc_ground_roster_synthetic.csv"
