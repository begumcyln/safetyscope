"""Stage E - compute key findings, draw report figures, write the executive summary.

Usage:
    python src/findings.py          (after src/pipeline.py and src/run_sql.py)

Outputs:
    reports/key_metrics.json        every number used in the summary
    reports/figures/*.png           static figures (matplotlib, Agg backend)
    reports/executive_summary.md

Memory: figures are drawn one at a time and closed immediately.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from safetyscope import config as C  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"  # validated categorical slots 1-2 (light mode)
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
BMHCA = "Butylphenyl methylpropional"
TPO = "Diphenyl(2,4,6-trimethylbenzoyl)phosphine oxide"
SOURCE_NOTE = ("Source: Safety Gate export (Cosmetics, 2025 filter), downloaded 27 Nov 2026; "
               "official XML weekly reports. Unit: alerts (notifications).")

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlecolor": INK, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6,
})


def load():
    a = pd.read_csv(C.PROCESSED_DIR / "alerts_clean.csv", low_memory=False,
                    parse_dates=["weekly_report_date", "first_measure_date", "publication_date"])
    s = pd.read_csv(C.PROCESSED_DIR / "alert_substances.csv")
    m = pd.read_csv(C.PROCESSED_DIR / "alert_measures.csv")
    return a, s, m


def pct(part, whole) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def compute(a, s, m) -> dict:
    n = len(a)
    chem = s[s["agent_type"] == "chemical"]
    sub_alerts = chem.groupby("substance")["alert_number"].nunique().sort_values(ascending=False)
    italy = a[a["notifying_country"] == "Italy"]
    rest = a[a["notifying_country"] != "Italy"]
    lag = (a["weekly_report_date"] - a["first_measure_date"]).dt.days
    ita_weekly = italy.groupby("weekly_report").size().sort_values(ascending=False)
    in_2025 = a[a["weekly_report_date"].dt.year == 2025]
    tpo = a[a["alert_number"].isin(chem.loc[chem["substance"] == TPO, "alert_number"])]
    known_origin = a[a["origin_country"] != "Unknown"]
    k = {
        "alerts": n,
        "alerts_chemical_any": int(a["is_chemical"].sum()),
        "alerts_microbiological": int(a["is_microbiological"].sum()),
        "distinct_chemicals": int(sub_alerts.size),
        "bmhca_alerts": int(sub_alerts[BMHCA]), "bmhca_pct": pct(sub_alerts[BMHCA], n),
        "top5_substances": {k_: int(v) for k_, v in sub_alerts.head(5).items()},
        "chemicals_in_one_alert": int((sub_alerts == 1).sum()),
        "fragrance_alerts": int((a["product_group"] == "Fragrance").sum()),
        "fragrance_pct": pct((a["product_group"] == "Fragrance").sum(), n),
        "fragrance_bmhca_pct": pct(((a["product_group"] == "Fragrance") & (a["primary_substance"] == BMHCA)).sum(),
                                   (a["product_group"] == "Fragrance").sum()),
        "edt_perfume_alerts": int(a["product_type"].isin(["Eau de toilette", "Perfume"]).sum()),
        "italy_alerts": len(italy), "italy_pct": pct(len(italy), n),
        "top3_notifier_pct": pct(a["notifying_country"].value_counts().head(3).sum(), n),
        "italy_bmhca_pct": pct((italy["primary_substance"] == BMHCA).sum(), len(italy)),
        "rest_bmhca_pct": pct((rest["primary_substance"] == BMHCA).sum(), len(rest)),
        "italy_ingredient_list_pct": pct(italy["based_on_ingredient_list"].sum(), len(italy)),
        "rest_ingredient_list_pct": pct(rest["based_on_ingredient_list"].sum(), len(rest)),
        "italy_measured_pct": pct(italy["has_measured_value"].sum(), len(italy)),
        "rest_measured_pct": pct(rest["has_measured_value"].sum(), len(rest)),
        "italy_domestic_origin_pct": pct(italy["origin_same_as_notifier"].sum(), len(italy)),
        "italy_weekly_reports": int(ita_weekly.size),
        "italy_top10_reports_pct": pct(ita_weekly.head(10).sum(), len(italy)),
        "italy_max_in_one_report": int(ita_weekly.iloc[0]), "italy_busiest_report": ita_weekly.index[0],
        "italy_median_lag_days": float((italy["weekly_report_date"] - italy["first_measure_date"]).dt.days.median()),
        "rest_median_lag_days": float((rest["weekly_report_date"] - rest["first_measure_date"]).dt.days.median()),
        "italy_measure_2023_2024_pct": pct((italy["first_measure_date"].dt.year.isin([2023, 2024])).sum(),
                                           italy["first_measure_date"].notna().sum()),
        "italy_compulsory_pct": pct(m[m["alert_number"].isin(italy["alert_number"]) & (m["measure_kind"] == "compulsory")]["alert_number"].nunique(), len(italy)),
        "median_lag_days": float(lag.median()), "lag_p25": float(lag.quantile(.25)), "lag_p75": float(lag.quantile(.75)),
        "ban_pct": pct(m.loc[m["measure_group"] == "Ban on marketing", "alert_number"].nunique(), n),
        "withdrawal_pct": pct(m.loc[m["measure_group"] == "Withdrawal from market", "alert_number"].nunique(), n),
        "recall_pct": pct(m.loc[m["measure_group"] == "Recall from end users", "alert_number"].nunique(), n),
        "destruction_pct": pct(m.loc[m["measure_group"] == "Destruction", "alert_number"].nunique(), n),
        "voluntary_any_pct": pct(m.loc[m["measure_kind"] == "voluntary", "alert_number"].nunique(), n),
        "origin_unknown": int((a["origin_country"] == "Unknown").sum()),
        "origin_eu_pct_of_known": pct(known_origin["origin_is_eu"].astype(str).eq("True").sum(), len(known_origin)),
        "origin_top_known": {k_: int(v) for k_, v in known_origin["origin_country"].value_counts().head(5).items()},
        "skin_lightening_alerts": int((a["product_group"] == "Skin lightening").sum()),
        **skin_lightening(a, m),
        "tpo_alerts": len(tpo),
        "tpo_before_sep2025": int((tpo["weekly_report_date"] < "2025-09-01").sum()),
        "tpo_from_sep2025": int((tpo["weekly_report_date"] >= "2025-09-01").sum()),
        "tpo_nail_pct": pct((tpo["product_group"] == "Nail products").sum(), len(tpo)),
        "reports_2025_with_alerts": int(in_2025["weekly_report"].nunique()),
        "busiest_month": in_2025["weekly_report_date"].dt.to_period("M").value_counts().idxmax().strftime("%Y-%m"),
        "busiest_month_alerts": int(in_2025["weekly_report_date"].dt.to_period("M").value_counts().max()),
    }
    return k


def skin_lightening(a, m) -> dict:
    sl = a[a["product_group"] == "Skin lightening"]
    known = sl[sl["origin_country"] != "Unknown"]
    meas = m[m["alert_number"].isin(sl["alert_number"])].groupby("measure_group")["alert_number"].nunique()
    top_notifier = sl["notifying_country"].value_counts()
    return {
        "sl_known_origin": len(known),
        "sl_non_eu_known": int(known["origin_is_eu"].astype(str).eq("False").sum()),
        "sl_border_rejected": int(meas.get("Import rejected at border", 0)),
        "sl_destroyed": int(meas.get("Destruction", 0)),
        "sl_top_notifier": top_notifier.index[0], "sl_top_notifier_alerts": int(top_notifier.iloc[0]),
    }


def _finish(fig, ax, title, subtitle, name):
    ax.set_title(title, loc="left", pad=22)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=INK2)
    fig.text(0.01, 0.01, SOURCE_NOTE, fontsize=7, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    C.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(C.FIGURES_DIR / name, dpi=160)
    plt.close(fig)


def hbar(series: pd.Series, title, subtitle, name, xlabel="Alerts", highlight=None):
    series = series.sort_values()
    fig, ax = plt.subplots(figsize=(8, 0.38 * len(series) + 1.4))
    colors = [ORANGE if highlight and i in highlight else BLUE for i in series.index]
    ax.barh(series.index, series.values, color=colors, height=0.62)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(xlabel)
    for y, v in enumerate(series.values):
        ax.text(v, y, f" {v:,}", va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, series.max() * 1.12)
    _finish(fig, ax, title, subtitle, name)


def figures(a, s, m, k):
    hbar(a["product_group"].value_counts(), "Fragrances account for 45% of alerts",
         "Alerts by product group (project-defined grouping of the Safety Gate 'Product' field)",
         "fig01_product_groups.png")

    chem = s[s["agent_type"] == "chemical"]
    top = chem.groupby("substance")["alert_number"].nunique().sort_values(ascending=False).head(10)
    abbr = chem.drop_duplicates("substance").set_index("substance")["abbreviation"]
    top.index = [f"{abbr.get(i)} ({i[:28]})" if isinstance(abbr.get(i), str) else i for i in top.index]
    hbar(top, f"One substance (BMHCA) appears in {k['bmhca_pct']}% of alerts",
         "Top 10 chemical substances named in alert risk texts (alerts can name several)", "fig02_top_substances.png")

    # Notifying country: BMHCA vs other, stacked
    top_c = a["notifying_country"].value_counts().head(10).index
    sub = a[a["notifying_country"].isin(top_c)]
    tab = pd.crosstab(sub["notifying_country"], sub["primary_substance"].eq(BMHCA)).reindex(top_c[::-1])
    tab.columns = ["Other substance / risk" if not c else "BMHCA" for c in tab.columns]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(tab.index, tab["BMHCA"], color=BLUE, height=0.62, label="BMHCA", edgecolor=SURFACE, linewidth=1)
    ax.barh(tab.index, tab["Other substance / risk"], left=tab["BMHCA"], color=ORANGE, height=0.62,
            label="Other substance / risk", edgecolor=SURFACE, linewidth=1)
    for y, (b, o) in enumerate(zip(tab["BMHCA"], tab["Other substance / risk"])):
        ax.text(b + o, y, f" {b + o:,}", va="center", fontsize=8, color=INK2)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Alerts")
    ax.legend(frameon=False, loc="lower right")
    _finish(fig, ax, f"Italy submitted {k['italy_pct']}% of alerts - {k['italy_bmhca_pct']}% of them on BMHCA",
            "Alerts by notifying country (top 10), split by primary substance. Counts are not safety rankings.",
            "fig03_notifying_countries.png")

    # Weekly trend 2025: Italy vs other
    w = a[a["weekly_report_date"].dt.year == 2025]
    wk = pd.crosstab(w["weekly_report_date"], w["notifying_country"].eq("Italy"))
    wk.columns = ["Other notifiers" if not c else "Italy" for c in wk.columns]
    idx = pd.date_range("2025-01-03", "2025-12-26", freq="W-FRI")
    wk = wk.reindex(idx, fill_value=0)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(wk.index, wk["Italy"], color=BLUE, lw=2, label="Italy")
    ax.plot(wk.index, wk["Other notifiers"], color=ORANGE, lw=2, label="Other notifiers")
    ax.axvline(pd.Timestamp("2025-09-01"), color=INK2, lw=0.8, ls=":")
    ax.text(pd.Timestamp("2025-09-04"), ax.get_ylim()[1] * 0.92, "TPO prohibition applies\n(1 Sep 2025)", fontsize=7, color=INK2)
    ax.set_ylabel("Alerts per weekly report")
    ax.legend(frameon=False)
    _finish(fig, ax, "Italian notifications arrive in batches",
            f"Alerts per 2025 weekly report. Top 10 reports hold {k['italy_top10_reports_pct']}% of Italy's alerts.",
            "fig04_weekly_trend.png")

    hbar(m.groupby("measure_group")["alert_number"].nunique(), "A ban on marketing is the usual corrective measure",
         "Alerts with at least one measure of each type (an alert can have several)", "fig05_measures.png")

    # Substance x product group heatmap (share of each group's alerts)
    top8 = chem.groupby("substance")["alert_number"].nunique().sort_values(ascending=False).head(8).index
    pair = chem[chem["substance"].isin(top8)].merge(a[["alert_number", "product_group"]], on="alert_number")
    groups = a["product_group"].value_counts().head(10).index
    mat = pd.crosstab(pair["substance"], pair["product_group"]).reindex(index=top8, columns=groups, fill_value=0)
    share = mat / a["product_group"].value_counts()[groups] * 100
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue_seq", ["#f4f8fd", "#9ec5f4", "#3987e5", "#1c5cab", "#0d366b"])
    fig, ax = plt.subplots(figsize=(10, 5.4))
    im = ax.imshow(share.values, cmap=cmap, aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(groups)), list(groups), fontsize=8, rotation=35, ha="right")
    labels = [f"{abbr.get(i)}" if isinstance(abbr.get(i), str) else i for i in top8]
    ax.set_yticks(range(len(top8)), labels, fontsize=8)
    ax.grid(False)
    for (i, j), v in pd.DataFrame(share.values).stack().items():
        if mat.values[i, j]:
            ax.text(j, i, f"{v:.0f}%", ha="center", va="center", fontsize=7, color="white" if v > 50 else INK)
    fig.colorbar(im, ax=ax, label="% of the product group's alerts", shrink=0.8)
    _finish(fig, ax, "Substances are specific to product types",
            "Share of each product group's alerts naming the substance (top 8 substances, top 10 groups)",
            "fig06_substance_product_heatmap.png")

    lag = (a["weekly_report_date"] - a["first_measure_date"]).dt.days.dropna()
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.hist(lag.clip(lower=0, upper=900), bins=36, color=BLUE, edgecolor=SURFACE, linewidth=1)
    ax.axvline(lag.median(), color=ORANGE, lw=2)
    ax.text(lag.median() + 10, ax.get_ylim()[1] * 0.9, f"median {lag.median():.0f} days", color=INK, fontsize=8)
    ax.set_xlabel("Days from first measure's entry into force to weekly report (capped at 900)")
    ax.set_ylabel("Alerts")
    _finish(fig, ax, "Alerts are published months after the measure",
            f"{len(lag):,} alerts with a dated measure", "fig07_publication_lag.png")


def summary_md(k: dict) -> str:
    t5 = list(k["top5_substances"].items())
    org = ", ".join(f"{c} ({v})" for c, v in k["origin_top_known"].items())
    return f"""# Executive Summary — SafetyScope

**Scope.** {k['alerts']:,} EU Safety Gate alerts in the *Cosmetics* category, selected by the portal's 2025 filter
(downloaded 27 November 2026). An *alert* is a notification by a national authority about a product it found
non-compliant. Counts describe enforcement activity, **not** how often products are unsafe, market shares or a ranking
of countries: no denominator (products on the market, inspections carried out) is available.

## Key findings (verified from the data)

1. **One substance dominates.** BMHCA (2-(4-tert-butylbenzyl)propionaldehyde, also known as Lilial) is named in
   **{k['bmhca_alerts']:,} alerts ({k['bmhca_pct']}%)**. The next substances are far behind: {t5[1][0]} ({t5[1][1]}),
   {t5[2][0]} ({t5[2][1]}), {t5[3][0]} ({t5[3][1]}). {k['distinct_chemicals']} distinct chemicals appear in total;
   {k['chemicals_in_one_alert']} of them in a single alert only. BMHCA has been on the EU list of prohibited cosmetic
   ingredients since 1 March 2022 (Regulation (EU) 2021/1902, see `docs/REGULATORY_CONTEXT.md`).
2. **Fragrances are the largest product group** with {k['fragrance_alerts']} alerts ({k['fragrance_pct']}%), almost all
   of them BMHCA ({k['fragrance_bmhca_pct']}%). Eau de toilette and perfume alone account for {k['edt_perfume_alerts']} alerts.
3. **Substances are product-specific.** TPO and TMPTA are nail-product substances ({k['tpo_nail_pct']}% of TPO alerts are nail
   products); hydroquinone, mercury and clobetasol propionate are concentrated in skin-lightening products
   ({k['skin_lightening_alerts']} alerts): {k['sl_non_eu_known']} of the {k['sl_known_origin']} with a known origin come from outside the EU,
   and {k['sl_border_rejected']} were rejected at the border ({k['sl_top_notifier']} notified {k['sl_top_notifier_alerts']} of them).
4. **Three countries submitted {k['top3_notifier_pct']}% of alerts**; Italy alone {k['italy_alerts']:,} ({k['italy_pct']}%).
5. **Notifying-country profiles differ sharply.** Italy, Czechia and Hungary notify almost exclusively BMHCA cases
   identified from the ingredient list. Germany, France and Northern Ireland notify fewer but more varied cases, often
   based on laboratory measurements and voluntary company measures (queries q06, q13).
6. **Corrective measures:** a ban on marketing is reported in {k['ban_pct']}% of alerts, withdrawal in {k['withdrawal_pct']}%,
   destruction in {k['destruction_pct']}%, recall from consumers in {k['recall_pct']}%. Voluntary (company-initiated) measures
   appear in {k['voluntary_any_pct']}% of alerts.
7. **Alerts are published long after the measure.** Median {k['median_lag_days']:.0f} days between the first measure's entry into
   force and the weekly report (interquartile range {k['lag_p25']:.0f}–{k['lag_p75']:.0f} days).
8. **Origin:** {k['origin_unknown']} alerts ({round(100*k['origin_unknown']/k['alerts'],1)}%) have unknown origin. Of the known origins,
   {k['origin_eu_pct_of_known']}% are EU member states; most frequent: {org}.

## Why does Italy account for so many notifications?

Evidence from the data (verified):

| Indicator | Italy | All other notifiers |
|---|---|---|
| Share of alerts naming BMHCA as primary substance | {k['italy_bmhca_pct']}% | {k['rest_bmhca_pct']}% |
| Share based on the product's ingredient list | {k['italy_ingredient_list_pct']}% | {k['rest_ingredient_list_pct']}% |
| Share with a laboratory measurement | {k['italy_measured_pct']}% | {k['rest_measured_pct']}% |
| Median days from first measure to weekly report | {k['italy_median_lag_days']:.0f} | {k['rest_median_lag_days']:.0f} |

- {k['italy_domestic_origin_pct']}% of Italy's alerts concern products of Italian origin; {k['italy_compulsory_pct']}% carry an
  authority-ordered (compulsory) measure.
- Italy's alerts are spread over {k['italy_weekly_reports']} weekly reports, but the 10 largest reports hold
  {k['italy_top10_reports_pct']}% of them (maximum {k['italy_max_in_one_report']} in {k['italy_busiest_report']}).
- {k['italy_measure_2023_2024_pct']}% of Italy's dated measures took effect in 2023–2024, although the alerts were published in 2025.

**Interpretation (hypothesis, not verified):** the pattern is consistent with a large-scale, label-based
enforcement of the BMHCA prohibition by Italian authorities — checking ingredient lists of products already on the
market — whose results were notified to Safety Gate in batches, often a year or more after the national measure.
The data cannot show *why* Italy did this, nor whether other countries found fewer cases or simply notified fewer:
notification practices, inspection priorities and market size all affect the counts, and none of them is in the data.

## Timing

Alerts are dated by the official weekly report in which they appeared. Activity in 2025 covered
{k['reports_2025_with_alerts']} weekly reports; the busiest month was {k['busiest_month']} ({k['busiest_month_alerts']} alerts).
**All {k['tpo_alerts']} TPO alerts appeared in weekly reports dated on or after 1 September 2025** ({k['tpo_before_sep2025']} before),
the date from which Regulation (EU) 2025/877 moved TPO to the list of prohibited substances. This timing is descriptive:
the data show the coincidence, not the authorities' reasons.

## What this means for a business audience (interpretation)

- **Fragrance and personal-care importers/distributors:** BMHCA-containing stock is the dominant enforcement issue in
  this period; ingredient-list screening alone triggers alerts, so label review is a low-cost control.
- **Nail-product suppliers:** TPO, TMPTA and HEMA recur; TPO's change from restricted to prohibited status from
  1 September 2025 makes it a substance to monitor.
- **Skin-lightening products from outside the EU** are named with mercury, hydroquinone and clobetasol propionate,
  and are mostly stopped at the external border (border rejection in {k['sl_border_rejected']} of {k['skin_lightening_alerts']} alerts) —
  relevant for import compliance checks.

## Limitations

- One export, one portal filter, whose exact definition is not documented (see `reports/date_investigation.md`).
- Counts are notifications, not prevalence; country comparisons reflect enforcement and reporting activity.
- Substance extraction is rule-based and evaluated against AI-produced labels pending human review
  (`reports/substance_extraction_evaluation.md`).
- Product groups are a project-defined classification.

Figures: `reports/figures/`. All numbers: `reports/key_metrics.json`, generated by `src/findings.py`.
"""


def main() -> None:
    a, s, m = load()
    k = compute(a, s, m)
    (C.REPORTS_DIR / "key_metrics.json").write_text(json.dumps(k, indent=2, default=str))
    figures(a, s, m, k)
    (C.REPORTS_DIR / "executive_summary.md").write_text(summary_md(k), encoding="utf-8")
    print(json.dumps(k, indent=2, default=str))


if __name__ == "__main__":
    main()
