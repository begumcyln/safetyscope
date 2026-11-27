import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from safetyscope import config as C  # noqa: E402


@pytest.fixture(scope="session")
def alerts():
    path = C.PROCESSED_DIR / "alerts_clean.csv"
    if not path.exists():
        pytest.skip("Run `python src/pipeline.py` first")
    return pd.read_csv(path, low_memory=False)


@pytest.fixture(scope="session")
def processed():
    names = ["alert_risk_types", "alert_measures", "alert_substances", "alert_also_found"]
    return {n: pd.read_csv(C.PROCESSED_DIR / f"{n}.csv") for n in names}
