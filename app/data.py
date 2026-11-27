"""Data access and shared helpers for the Streamlit app (read-only)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK2, GRID = "#52514e", "#e6e5e1"
BMHCA = "Butylphenyl methylpropional"
ATTRIBUTION = ("Alerts from the Rapid Alert System for dangerous non-food products, published free of charge on the "
               "Safety Gate website (https://ec.europa.eu/safety-gate-alerts) © European Union, 2005 – 2026")

ALERT_COLS = [
    "alert_number", "case_url", "alert_level", "user_type", "notifying_country", "origin_country", "origin_is_eu",
    "origin_same_as_notifier", "product_type", "product_group", "product_name", "brand", "counterfeit",
    "risk_type", "risk_description", "primary_substance", "chemical_substance_count", "based_on_ingredient_list",
    "has_measured_value", "alert_states_prohibited", "weekly_report", "weekly_report_date", "publication_date",
    "first_measure_date", "alert_number_year",
]


@st.cache_data(show_spinner=False)
def load() -> dict[str, pd.DataFrame]:
    alerts = pd.read_csv(PROCESSED / "alerts_clean.csv", usecols=ALERT_COLS, low_memory=False,
                         parse_dates=["weekly_report_date", "publication_date", "first_measure_date"])
    for col in ["notifying_country", "origin_country", "product_group", "product_type", "risk_type", "alert_level"]:
        alerts[col] = alerts[col].astype("category")
    subs = pd.read_csv(PROCESSED / "alert_substances.csv",
                       usecols=["alert_number", "substance", "abbreviation", "agent_type", "substance_group", "confidence", "is_primary"])
    measures = pd.read_csv(PROCESSED / "alert_measures.csv",
                           usecols=["alert_number", "measure_kind", "economic_operator", "measure_category", "measure_group", "entry_into_force_date"])
    risks = pd.read_csv(PROCESSED / "alert_risk_types.csv", usecols=["alert_number", "risk_type"])
    return {"alerts": alerts, "subs": subs, "measures": measures, "risks": risks}


@st.cache_data(show_spinner=False)
def load_json(name: str) -> dict:
    path = PROCESSED / name if (PROCESSED / name).exists() else REPORTS / name
    return json.loads(path.read_text()) if path.exists() else {}


@st.cache_data(show_spinner=False)
def load_csv(path: str) -> pd.DataFrame:
    p = ROOT / path
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def substance_label(name: str, abbr) -> str:
    return f"{abbr} — {name}" if isinstance(abbr, str) and abbr and abbr != name else name


def style(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=30, b=10), template="simple_white",
        font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=12, color="#1f1f1d"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=INK2))
    fig.update_yaxes(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=INK2))
    return fig


def hbar(series: pd.Series, x_title: str = "Alerts", height: int | None = None, color: str = BLUE) -> go.Figure:
    series = series.sort_values()
    fig = go.Figure(go.Bar(
        x=series.values, y=[str(i) for i in series.index], orientation="h", marker_color=color,
        text=[f"{v:,}" for v in series.values], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:,} alerts<extra></extra>",
    ))
    fig.update_xaxes(title=x_title, showgrid=True, range=[0, max(series.max(), 1) * 1.15])  # headroom for labels
    fig.update_yaxes(showgrid=False)
    return style(fig, height or max(260, 28 * len(series) + 80))


def pct(part, whole) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "–"
