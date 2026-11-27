"""Page implementations for the SafetyScope Streamlit app.

Each function renders one page. The sidebar filters are applied once in
streamlit_app.py and the filtered alerts are shared via st.session_state.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data import (ATTRIBUTION, BLUE, BMHCA, ORANGE, hbar, load, load_csv, load_json, pct,  # noqa: F401
                  style, substance_label)

D = load()
ALERTS, SUBS, MEASURES = D["alerts"], D["subs"], D["measures"]


def current() -> pd.DataFrame:
    return st.session_state.get("filtered", ALERTS)


def sidebar_filters() -> pd.DataFrame:
    st.sidebar.markdown("### Filters")
    a = ALERTS
    countries = st.sidebar.multiselect("Notifying country", sorted(a["notifying_country"].cat.categories))
    groups = st.sidebar.multiselect("Product group", sorted(a["product_group"].cat.categories))
    sub_names = SUBS["substance"].value_counts().index.tolist()
    substances = st.sidebar.multiselect("Substance / agent", sub_names)
    risk_types = st.sidebar.multiselect("Risk type", sorted(D["risks"]["risk_type"].unique()))
    dmin, dmax = a["weekly_report_date"].min().date(), a["weekly_report_date"].max().date()
    dates = st.sidebar.date_input("Weekly report date", (dmin, dmax), min_value=dmin, max_value=dmax)

    mask = pd.Series(True, index=a.index)
    if countries:
        mask &= a["notifying_country"].isin(countries)
    if groups:
        mask &= a["product_group"].isin(groups)
    if substances:
        mask &= a["alert_number"].isin(SUBS.loc[SUBS["substance"].isin(substances), "alert_number"])
    if risk_types:
        mask &= a["alert_number"].isin(D["risks"].loc[D["risks"]["risk_type"].isin(risk_types), "alert_number"])
    if isinstance(dates, tuple) and len(dates) == 2:
        mask &= a["weekly_report_date"].between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))
    filtered = a[mask]
    st.sidebar.markdown(f"**{len(filtered):,}** of {len(a):,} alerts selected")
    st.sidebar.caption("Unit: one Safety Gate alert (notification). Counts are not defect rates, "
                       "market shares or national safety rankings.")
    return filtered


def empty_guard(a: pd.DataFrame) -> bool:
    if a.empty:
        st.info("No alerts match the current filters.")
        return True
    return False


def subs_for(a):
    return SUBS[SUBS["alert_number"].isin(a["alert_number"])]


def measures_for(a):
    return MEASURES[MEASURES["alert_number"].isin(a["alert_number"])]


def executive_overview():
    a = current()
    st.title("Executive Overview")
    st.markdown('<p class="caption-note">EU Safety Gate alerts in the Cosmetics category selected by the portal\'s 2025 '
                'filter (export downloaded 27 Nov 2026), enriched with official weekly-report dates.</p>', unsafe_allow_html=True)
    if empty_guard(a):
        return
    s = subs_for(a)
    chem = s[s["agent_type"] == "chemical"]
    lag = (a["weekly_report_date"] - a["first_measure_date"]).dt.days
    c = st.columns(5)
    c[0].metric("Alerts", f"{len(a):,}")
    c[1].metric("Distinct chemicals named", f"{chem['substance'].nunique():,}")
    c[2].metric("Alerts naming BMHCA", pct(s.loc[s["substance"] == BMHCA, "alert_number"].nunique(), len(a)),
                help="Share of selected alerts whose risk text names BMHCA (butylphenyl methylpropional).")
    c[3].metric("Notifying countries", f"{a['notifying_country'].nunique()}")
    c[4].metric("Median days measure → report", f"{lag.median():.0f}" if lag.notna().any() else "–",
                help="Days from the first corrective measure's entry into force to the weekly report.")

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Alerts by product group")
        st.plotly_chart(hbar(a["product_group"].value_counts().loc[lambda x: x > 0]), width="stretch")
    with right:
        st.subheader("Most frequent chemical substances")
        top = chem.groupby(["substance", "abbreviation"], dropna=False)["alert_number"].nunique().sort_values(ascending=False).head(10)
        top.index = [substance_label(n, ab)[:45] for n, ab in top.index]
        st.plotly_chart(hbar(top), width="stretch")

    st.subheader("Alerts per weekly report")
    # A handful of alerts appeared in 2020/2024 weekly reports (re-published later); plotting them
    # would stretch the axis over five years, so the trend starts in December 2024.
    start = pd.Timestamp("2024-12-01")
    recent = a[a["weekly_report_date"] >= start]
    if recent.empty:
        recent = a
    wk = recent.groupby([pd.Grouper(key="weekly_report_date", freq="W-FRI"),
                         recent["notifying_country"].eq("Italy").map({True: "Italy", False: "Other notifiers"})],
                        observed=True).size().unstack(fill_value=0)
    fig = go.Figure()
    for col, color in [("Italy", BLUE), ("Other notifiers", ORANGE)]:
        if col in wk:
            fig.add_scatter(x=wk.index, y=wk[col], mode="lines", name=col, line=dict(color=color, width=2),
                            hovertemplate="%{x|%d %b %Y}: %{y} alerts<extra>" + col + "</extra>")
    fig.update_yaxes(title="Alerts")
    st.plotly_chart(style(fig, 320), width="stretch")
    hidden = len(a) - len(recent)
    st.caption("Italy is shown separately because it submitted about two thirds of all alerts; see Market Analysis."
               + (f" {hidden} alert(s) from weekly reports before December 2024 are not plotted." if hidden else ""))


def chemical_intelligence():
    a = current()
    st.title("Chemical Intelligence")
    if empty_guard(a):
        return
    s = subs_for(a).merge(a[["alert_number", "product_group", "notifying_country", "origin_country", "weekly_report_date"]], on="alert_number")
    chem = s[s["agent_type"] == "chemical"]
    c = st.columns(4)
    c[0].metric("Alerts naming a chemical", f"{chem['alert_number'].nunique():,}")
    c[1].metric("Distinct chemicals", f"{chem['substance'].nunique()}")
    c[2].metric("Alerts naming >1 chemical", f"{(chem.groupby('alert_number').size() > 1).sum():,}")
    c[3].metric("Microbiological agents", f"{s.loc[s['agent_type'] == 'microorganism', 'alert_number'].nunique():,} alerts")

    st.subheader("Substance × product group")
    top = chem["substance"].value_counts().head(10).index
    groups = a["product_group"].value_counts().loc[lambda x: x > 0].head(10).index
    mat = pd.crosstab(chem["substance"], chem["product_group"]).reindex(index=top, columns=groups, fill_value=0)
    abbr = SUBS.drop_duplicates("substance").set_index("substance")["abbreviation"]
    group_totals = a["product_group"].value_counts().reindex(groups)
    share = (mat / group_totals.values * 100).round(1)
    text = [[f"{v:.0f}%" if n else "" for v, n in zip(srow, nrow)] for srow, nrow in zip(share.values, mat.values)]
    fig = go.Figure(go.Heatmap(
        z=share.values, x=[str(g) for g in groups], y=[substance_label(i, abbr.get(i))[:40] for i in top],
        customdata=mat.values, zmin=0, zmax=100,
        colorscale=[[0, "#f4f8fd"], [0.25, "#9ec5f4"], [0.5, "#3987e5"], [0.75, "#1c5cab"], [1, "#0d366b"]],
        text=text, texttemplate="%{text}",
        hovertemplate="%{y}<br>%{x}: %{customdata} alerts (%{z:.1f}% of the group)<extra></extra>",
        colorbar=dict(title="% of group")))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig, 420), width="stretch")
    st.caption("Cell = share of the product group's selected alerts that name the substance. Columns can exceed 100% "
               "in total because one alert can name several substances.")

    st.subheader("Substance profile")
    options = chem["substance"].value_counts().index.tolist()
    choice = st.selectbox("Select a substance", options, format_func=lambda n: substance_label(n, abbr.get(n)))
    sel = s[s["substance"] == choice]
    ids = sel["alert_number"].unique()
    info = SUBS[SUBS["substance"] == choice].iloc[0]
    st.markdown(f"**{choice}** · group: {info['substance_group']} · named in **{len(ids):,}** selected alerts")
    l, m, r = st.columns(3)
    with l:
        st.caption("Product groups")
        st.plotly_chart(hbar(sel["product_group"].value_counts().loc[lambda x: x > 0].head(8), height=280), width="stretch")
    with m:
        st.caption("Countries of origin (known only)")
        st.plotly_chart(hbar(sel.loc[sel["origin_country"] != "Unknown", "origin_country"].value_counts().loc[lambda x: x > 0].head(8), height=280), width="stretch")
    with r:
        st.caption("Corrective measures")
        st.plotly_chart(hbar(MEASURES[MEASURES["alert_number"].isin(ids)].groupby("measure_group")["alert_number"].nunique().head(8), height=280), width="stretch")
    st.caption("Mentions are extracted from the alert's risk text with a rule-based dictionary. A statement that a "
               "substance is 'prohibited' is the notifying authority's wording, not a legal assessment by this project.")


def market_analysis():
    a = current()
    st.title("Market Analysis")
    if empty_guard(a):
        return
    st.info("Notification counts reflect each authority's enforcement and reporting activity. Without data on "
            "inspections or products on the market they cannot be read as national safety rankings.", icon="ℹ️")
    st.subheader("Notifying-country profiles")
    m = measures_for(a)
    vol = set(m.loc[m["measure_kind"] == "voluntary", "alert_number"])
    prof = a.groupby("notifying_country", observed=True).agg(
        alerts=("alert_number", "size"),
        pct_bmhca=("primary_substance", lambda x: 100 * (x == BMHCA).mean()),
        pct_ingredient_list=("based_on_ingredient_list", lambda x: 100 * x.mean()),
        pct_lab_measurement=("has_measured_value", lambda x: 100 * x.mean()),
        pct_origin_unknown=("origin_country", lambda x: 100 * (x == "Unknown").mean()),
        pct_domestic_origin=("origin_same_as_notifier", lambda x: 100 * x.mean()),
        product_types=("product_type", "nunique"),
    ).sort_values("alerts", ascending=False)
    prof["pct_voluntary_measure"] = a.groupby("notifying_country", observed=True)["alert_number"].apply(
        lambda ids: 100 * ids.isin(vol).mean()).reindex(prof.index)
    prof.insert(1, "share_of_alerts", 100 * prof["alerts"] / prof["alerts"].sum())
    st.dataframe(prof.round(1), width="stretch", column_config={
        c: st.column_config.ProgressColumn(c.replace("_", " "), format="%.1f%%", min_value=0, max_value=100)
        for c in prof.columns if c.startswith("pct_") or c == "share_of_alerts"})

    l, r = st.columns(2)
    with l:
        st.subheader("Country of origin (known)")
        known = a[a["origin_country"] != "Unknown"]
        st.plotly_chart(hbar(known["origin_country"].value_counts().loc[lambda x: x > 0].head(15)), width="stretch")
        st.caption(f"{(a['origin_country'] == 'Unknown').sum():,} selected alerts have unknown origin and are not shown.")
    with r:
        st.subheader("EU vs non-EU origin")
        eu = a["origin_is_eu"].astype(str).map({"True": "EU member state", "False": "Non-EU"}).fillna("Unknown")
        st.plotly_chart(hbar(eu.value_counts()), width="stretch")
        st.subheader("Notifier → origin (top flows)")
        flows = a[a["origin_country"] != "Unknown"].groupby(["notifying_country", "origin_country"], observed=True).size()
        st.dataframe(flows.sort_values(ascending=False).head(12).rename("alerts").reset_index(), hide_index=True, width="stretch")


def product_analysis():
    a = current()
    st.title("Product & Corrective Measure Analysis")
    if empty_guard(a):
        return
    m = measures_for(a)
    c = st.columns(4)
    c[0].metric("Product types", f"{a['product_type'].nunique()}")
    c[1].metric("Alerts with a ban on marketing", pct(m.loc[m["measure_group"] == "Ban on marketing", "alert_number"].nunique(), len(a)))
    c[2].metric("Alerts with a recall", pct(m.loc[m["measure_group"] == "Recall from end users", "alert_number"].nunique(), len(a)))
    c[3].metric("Alerts with a voluntary measure", pct(m.loc[m["measure_kind"] == "voluntary", "alert_number"].nunique(), len(a)))
    l, r = st.columns(2)
    with l:
        st.subheader("Top product types")
        st.plotly_chart(hbar(a["product_type"].value_counts().loc[lambda x: x > 0].head(15)), width="stretch")
    with r:
        st.subheader("Corrective measures")
        st.plotly_chart(hbar(m.groupby("measure_group")["alert_number"].nunique()), width="stretch")
        st.caption("Alerts with at least one measure of the type; one alert can have several measures.")
    st.subheader("Measure type by product group")
    mg = m.merge(a[["alert_number", "product_group"]], on="alert_number")
    tab = mg.groupby(["product_group", "measure_kind"], observed=True)["alert_number"].nunique().unstack(fill_value=0)
    fig = go.Figure()
    for kind, color in [("compulsory", BLUE), ("voluntary", ORANGE)]:
        if kind in tab:
            fig.add_bar(y=[str(i) for i in tab.index], x=tab[kind], name=f"{kind.title()} (alerts)", orientation="h",
                        marker_color=color, hovertemplate="%{y}: %{x} alerts<extra>" + kind + "</extra>")
    fig.update_layout(barmode="group")
    st.plotly_chart(style(fig, 420), width="stretch")
    st.subheader("Economic operator addressed / acting")
    st.plotly_chart(hbar(m.groupby("economic_operator")["alert_number"].nunique(), height=260), width="stretch")


def alert_explorer():
    a = current()
    st.title("Alert Explorer")
    query = st.text_input("Search product, name, brand, alert number or risk text", placeholder="e.g. hydroquinone, Nivea, SR/01834/25")
    view = a
    if query:
        q = query.lower()
        hay = (a["alert_number"] + " " + a["product_type"].astype(str) + " " + a["product_name"].fillna("") + " "
               + a["brand"].fillna("") + " " + a["risk_description"].fillna("")).str.lower()
        view = a[hay.str.contains(q, regex=False)]
    st.caption(f"{len(view):,} alerts")
    cols = ["alert_number", "case_url", "weekly_report_date", "notifying_country", "origin_country", "product_type", "product_name",
            "brand", "primary_substance", "risk_type", "risk_description"]
    out = view[cols].sort_values("weekly_report_date", ascending=False)
    st.dataframe(out, hide_index=True, width="stretch", height=520, column_config={
        "case_url": st.column_config.LinkColumn("Safety Gate case", display_text="Open ↗"),
        "weekly_report_date": st.column_config.DateColumn("Weekly report", format="YYYY-MM-DD"),
        "risk_description": st.column_config.TextColumn("Risk (Safety Gate text)", width="large"),
    })
    st.download_button("Download filtered alerts (CSV)", out.to_csv(index=False).encode("utf-8"),
                       file_name="safetyscope_filtered_alerts.csv", mime="text/csv")
    st.caption(ATTRIBUTION)


def data_quality():
    st.title("Data Quality & Provenance")
    run = load_json("pipeline_run_summary.json")
    src = (run.get("source_files") or [{}])[0]
    c = st.columns(4)
    c[0].metric("Source rows", f"{src.get('rows', 0):,}")
    c[1].metric("Alerts matched to official weekly report", f"{run.get('alerts_matched_in_xml', 0):,}")
    c[2].metric("Substance mentions", f"{run.get('substance_mentions', 0):,}")
    c[3].metric("Uncertain extractions", f"{run.get('uncertain_candidates', 0)}")
    st.subheader("Provenance")
    st.markdown(f"""
- **Source export:** `{src.get('file', '')}` — downloaded from the Safety Gate portal on 27 Nov 2026 (Cosmetics, 2025 filter); SHA-256 `{src.get('sha256', '')[:16]}…`
- **Enrichment:** official Safety Gate weekly-report XML (public download), {run.get('xml_reports_cached', 0)} reports cached
- **Pipeline run:** {run.get('run_started_utc', '')} UTC (`python src/pipeline.py`)
- **Dates:** time series use the *weekly report date*. Alert-number year, XML publication date and measure dates
  have different meanings and are kept separate (see `reports/date_investigation.md`).""")
    l, r = st.columns(2)
    with l:
        st.subheader("Flagged data-quality issues")
        issues = load_csv("data/processed/data_quality_issues.csv")
        if not issues.empty:
            st.plotly_chart(hbar(issues["issue_type"].value_counts(), x_title="Records", height=280), width="stretch")
    with r:
        st.subheader("Excel validation checkpoints")
        st.dataframe(load_csv("reports/tables/excel_checkpoint_validation.csv"), hide_index=True, width="stretch")
    st.subheader("Substance extraction evaluation")
    st.dataframe(load_csv("data/evaluation/extraction_metrics.csv"), hide_index=True, width="stretch")
    st.warning("Reference labels for this evaluation were produced by an AI assistant and are pending human review; "
               "the metrics are an agreement check, not validated accuracy.", icon="⚠️")
    st.subheader("Licence and attribution")
    st.markdown(f"Reuse of Safety Gate information is authorised provided the original meaning of the alerts is not "
                f"distorted and the source is acknowledged:\n\n> {ATTRIBUTION}\n\nBrands shown in alerts may have been "
                "used by third parties without the owner's permission (Safety Gate disclaimer).")


