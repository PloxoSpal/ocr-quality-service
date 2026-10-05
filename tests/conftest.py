import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from synthetic import make_page

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = Path(os.environ.get("OCRQ_DATASET_DIR", REPO_ROOT / "dataset"))


@pytest.fixture(scope="session")
def clean_page():
    return make_page()


@pytest.fixture(scope="session")
def dataset_dir() -> Path:
    if not list(DATASET_DIR.glob("images/*.png")):
        pytest.skip(f"dataset not found at {DATASET_DIR} (put the images there)")
    return DATASET_DIR
