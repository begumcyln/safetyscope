"""Headless smoke tests for the Streamlit app: every page renders without exceptions."""

from pathlib import Path

import pytest

from safetyscope import config as C

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")
PAGES = ["overview", "chemicals", "markets", "products", "explorer", "data_quality"]

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _needs_data():
    if not (C.PROCESSED_DIR / "alerts_clean.csv").exists():
        pytest.skip("Run `python src/pipeline.py` first")


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.switch_page(f"views/{page}.py").run()
    assert not at.exception, at.exception
    assert at.title, f"page {page} rendered no title"


def test_overview_kpis_match_dataset():
    at = AppTest.from_file(APP, default_timeout=60).run()
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Alerts"] == "1,714"
    assert metrics["Alerts naming BMHCA"] == "86.8%"


def test_country_filter_reduces_selection():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.sidebar.multiselect[0].select("Czechia").run()
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Alerts"] == "214"
    assert not at.exception


def test_explorer_search():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.switch_page("views/explorer.py").run()
    at.text_input[0].input("hydroquinone").run()
    assert not at.exception
    assert any("alerts" in c.value for c in at.caption)
