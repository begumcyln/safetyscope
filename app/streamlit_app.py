"""SafetyScope — European Cosmetics Safety Intelligence (Streamlit app).

Run:  streamlit run app/streamlit_app.py
Reads only the processed files in data/processed/ (run src/pipeline.py first).
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

st.set_page_config(page_title="SafetyScope", page_icon="🔎", layout="wide")
st.markdown("""
<style>
  .block-container {padding-top: 1.6rem; max-width: 1400px;}
  [data-testid="stMetric"] {background: #f7f7f5; border: 1px solid #e6e5e1; border-radius: 6px; padding: 10px 14px;}
  [data-testid="stMetricLabel"] p {font-size: 0.8rem; color: #52514e;}
  h1 {font-size: 1.6rem !important; font-weight: 650 !important;}
  h2, h3 {font-weight: 600 !important;}
  .caption-note {color: #52514e; font-size: 0.82rem;}
</style>""", unsafe_allow_html=True)


from page_views import sidebar_filters  # noqa: E402

PAGES = [
    st.Page("views/overview.py", title="Executive Overview", icon="📊", url_path="overview", default=True),
    st.Page("views/chemicals.py", title="Chemical Intelligence", icon="🧪", url_path="chemicals"),
    st.Page("views/markets.py", title="Market Analysis", icon="🌍", url_path="markets"),
    st.Page("views/products.py", title="Product Analysis", icon="📦", url_path="products"),
    st.Page("views/explorer.py", title="Alert Explorer", icon="🔍", url_path="explorer"),
    st.Page("views/data_quality.py", title="Data Quality", icon="✅", url_path="data-quality"),
]
nav = st.navigation(PAGES)
st.sidebar.markdown("## SafetyScope")
st.sidebar.caption("European Cosmetics Safety Intelligence")
st.session_state["filtered"] = sidebar_filters()
nav.run()
