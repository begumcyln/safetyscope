"""Transform step: raw export rows -> analysis-ready tables.

Output tables (one row per ...):
* alerts            - alert (original and cleaned values side by side)
* alert_risk_types  - alert x risk type        (multivalued "Risk type")
* alert_measures    - alert x measure          (parsed measure blocks)
* alert_also_found  - alert x additional country ("also in" field)
* alert_substances  - alert x substance mention (rule-based NLP)
* substance_candidates - uncertain, non-dictionary candidates for review
"""

from __future__ import annotations

import re

import pandas as pd

from . import measures as M
from . import standardize as S
from . import substances as SUB

COLUMN_NAMES = {
    "Type of alert": "alert_level",
    "Type": "user_type",
    "Alert number": "alert_number",
    "Alert submitted by": "notifying_country_raw",
    "Country of origin": "origin_country_raw",
    "Counterfeit": "counterfeit",
    "Risk type": "risk_type_raw",
    "Risk legal provision": "legal_provision_raw",
    "Product": "product_raw",
    "Name": "product_name_raw",
    "Description": "description",
    "Brand": "brand_raw",
    "Category": "category",
    "Type / number of model": "model",
    "OECD Portal category": "oecd_category",
    "Risk": "risk_description_raw",
    "Compulsory measures": "compulsory_measures_raw",
    "Voluntary measures": "voluntary_measures_raw",
    "Products were found and measures were taken also in": "also_found_in_raw",
    "Company recall page": "company_recall_page",
    "URL of Case": "case_url",
    "Barcode": "barcode",
    "Batch number": "batch_number",
    "Packaging description": "packaging_description",
    "Online trader": "online_trader",
}

ALERT_NUMBER_RE = re.compile(r"^(?P<prefix>[A-Z0-9]+)/(?P<seq>\d{5})/(?P<yy>\d{2})$")

# Measure category variants -> grouped category (original kept alongside)
MEASURE_GROUPS = [
    ("Ban on marketing", r"^ban on the marketing|temporary ban"),
    ("Withdrawal from market", r"^withdrawal"),
    ("Recall from end users", r"^recall"),
    ("Destruction", r"^destruction|awaiting destruction"),
    ("Import rejected at border", r"^import rejected"),
    ("Stop of sales", r"^stop of sales"),
    ("Online listing removed", r"removal of this product listing"),
    ("Warning consumers", r"^warning consumers"),
    ("Seizure / confiscation", r"seiz|confiscat"),
    ("Marketing subject to conditions", r"prior conditions"),
]


def measure_group(category: str | None) -> str | None:
    if not category:
        return None
    for group, pattern in MEASURE_GROUPS:
        if re.search(pattern, category, re.I):
            return group
    return "Other"


def build_alerts(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(columns=COLUMN_NAMES).copy()

    # 1. Whitespace / encoding normalisation for every text column. The original
    #    multi-line measure texts are kept unchanged because their line breaks
    #    carry structure; they are parsed separately.
    keep_linebreaks = {"compulsory_measures_raw", "voluntary_measures_raw"}
    text_cols = [c for c in df.columns if c not in ("source_row", "source_file") and c not in keep_linebreaks]
    normalized = df[text_cols].apply(lambda col: col.map(S.normalize_text))
    # Keep *_raw columns truly raw; write normalised copies to new columns.
    for col in text_cols:
        if col.endswith("_raw"):
            df[col.replace("_raw", "")] = normalized[col]
        else:
            df[col] = normalized[col]

    # 2. Alert ID validation and decomposition
    parts = df["alert_number"].str.extract(ALERT_NUMBER_RE)
    df["alert_number_valid"] = parts["prefix"].notna()
    df["alert_prefix"] = parts["prefix"]
    df["alert_sequence"] = pd.to_numeric(parts["seq"], errors="coerce").astype("Int64")
    df["alert_number_year"] = (2000 + pd.to_numeric(parts["yy"], errors="coerce")).astype("Int64")
    df["case_id"] = df["case_url"].str.extract(r"alertDetail/(\d+)")[0]

    # 3. Countries
    df["notifying_country"] = df["notifying_country"].map(S.country_display)
    df["notifying_country_iso2"] = df["notifying_country_raw"].map(S.country_iso2)
    df["origin_country"] = df["origin_country"].map(S.country_display)
    df["origin_country_iso2"] = df["origin_country_raw"].map(S.country_iso2)
    df["origin_known"] = df["origin_country"].ne("Unknown")
    df["origin_is_eu"] = df["origin_country_raw"].map(S.is_eu_member)
    df["origin_same_as_notifier"] = df["origin_country"].eq(df["notifying_country"])

    # 4. Products and brands
    df["product_type"] = df["product_raw"].map(S.standardize_product)
    df["product_group"] = df["product_type"].map(S.product_group)
    df["brand_key"] = df["brand_raw"].map(S.brand_key)
    df["brand"] = S.brand_display_names(df["brand_raw"])
    df["brand_missing"] = df["brand"].isna()
    df["product_name"] = df["product_name"]

    # 5. Risk type (multivalued): keep the original combined label and a count
    df["risk_type_count"] = df["risk_type"].str.split(",").map(len)
    df["is_chemical"] = df["risk_type"].str.contains("Chemical", na=False)
    df["is_microbiological"] = df["risk_type"].str.contains("Microbiological", na=False)

    # 6. Legal provision: normalised text (trailing full stops, spacing)
    df["legal_provision"] = df["legal_provision"].str.rstrip(". ").str.replace(
        "Cosmetic Product Regulation", "Cosmetic Products Regulation", regex=False)

    # 7. Risk description flags (attributed to the alert wording)
    flags = df["risk_description_raw"].map(SUB.text_flags).apply(pd.Series)
    df = pd.concat([df, flags], axis=1)

    df["counterfeit"] = df["counterfeit"].fillna("Unknown")
    return df


def build_risk_types(alerts: pd.DataFrame) -> pd.DataFrame:
    rows = alerts[["alert_number", "risk_type"]].copy()
    rows["risk_type"] = rows["risk_type"].str.split(",")
    rows = rows.explode("risk_type")
    rows["risk_type"] = rows["risk_type"].str.strip()
    rows["is_primary"] = ~rows.duplicated("alert_number")
    return rows.reset_index(drop=True)


def build_measures(alerts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for alert_number, comp, vol in alerts[["alert_number", "compulsory_measures_raw", "voluntary_measures_raw"]].itertuples(index=False):
        for kind, text in (("compulsory", comp), ("voluntary", vol)):
            for i, measure in enumerate(M.parse_measures(text, kind), start=1):
                measure.update({"alert_number": alert_number, "measure_seq": i})
                rows.append(measure)
    out = pd.DataFrame(rows)
    out["measure_group"] = out["measure_category"].map(measure_group)
    cols = ["alert_number", "measure_kind", "measure_seq", "economic_operator", "measure_category",
            "measure_group", "entry_into_force_raw", "entry_into_force_date", "parsed_ok"]
    return out[cols]


def build_also_found(alerts: pd.DataFrame) -> pd.DataFrame:
    rows = alerts[["alert_number", "also_found_in"]].dropna().copy()
    rows["country_raw"] = rows["also_found_in"].str.split(",")
    rows = rows.explode("country_raw")
    rows["country_raw"] = rows["country_raw"].str.strip()
    rows["country"] = rows["country_raw"].map(S.country_display)
    return rows[["alert_number", "country_raw", "country"]].reset_index(drop=True)


def build_substances(alerts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mentions, candidates = [], []
    for alert_number, text in alerts[["alert_number", "risk_description_raw"]].itertuples(index=False):
        found = SUB.extract_mentions(text)
        for order, m in enumerate(found, start=1):
            mentions.append({
                "alert_number": alert_number, "mention_order": order, "substance": m.substance,
                "abbreviation": m.abbreviation, "agent_type": m.agent_type, "substance_group": m.substance_group,
                "cas_number": m.cas_number, "matched_text": m.matched_text,
                "method": m.method, "confidence": m.confidence,
            })
        for cand in SUB.extract_candidates(text, found):
            candidates.append({"alert_number": alert_number, "candidate_text": cand,
                               "method": "generic_pattern", "confidence": "uncertain"})
    mention_df = pd.DataFrame(mentions)
    mention_df["is_primary"] = mention_df["mention_order"].eq(1)
    return mention_df, pd.DataFrame(candidates, columns=["alert_number", "candidate_text", "method", "confidence"])


def add_xml_enrichment(alerts: pd.DataFrame, xml_alerts: pd.DataFrame) -> pd.DataFrame:
    """Attach publication date and weekly report from the official XML (if cached)."""
    if xml_alerts.empty:
        alerts["publication_date"] = pd.NaT
        alerts["weekly_report"] = None
        alerts["weekly_report_date"] = pd.NaT
        alerts["xml_matched"] = False
        return alerts
    x = xml_alerts.rename(columns={"caseNumber": "alert_number"})
    x["publication_date"] = pd.to_datetime(x["publicationDate"], format="%d-%m-%Y", errors="coerce")
    x["weekly_report_date"] = pd.to_datetime(x["report_date"], format="%d/%m/%Y", errors="coerce")
    x = x.sort_values("weekly_report_date").drop_duplicates("alert_number", keep="first")
    x = x[["alert_number", "publication_date", "report_reference", "weekly_report_date", "category"]].rename(
        columns={"report_reference": "weekly_report", "category": "xml_category"})
    out = alerts.merge(x, on="alert_number", how="left")
    out["xml_matched"] = out["weekly_report"].notna()
    return out
