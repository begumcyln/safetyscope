"""Load step: write the processed tables into a SQLite database (sql/schema.sql)."""

from __future__ import annotations

import sqlite3

import pandas as pd

from . import standardize as S
from .config import DB_PATH, ROOT
from .extract import EXPECTED_COLUMNS

SCHEMA = ROOT / "sql" / "schema.sql"


def _iso(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d").where(lambda s: s.notna(), None)


def _none(df: pd.DataFrame) -> pd.DataFrame:
    """pandas NaN/NA -> None so SQLite stores NULL."""
    return df.astype(object).where(pd.notna(df), None)


def build_database(alerts, risk_types, measures, also_found, substances, candidates, raw) -> dict:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA.read_text())

    # Dimensions
    labels = set(alerts["notifying_country_raw"]) | set(alerts["origin_country_raw"])
    country = pd.DataFrame(
        [(S.country_display(lbl), lbl, S.country_iso2(lbl), S.is_eu_member(lbl)) for lbl in sorted(labels)],
        columns=["country_name", "safety_gate_label", "iso2", "is_eu_member"],
    )
    country.pipe(_none).to_sql("country", con, if_exists="append", index=False)

    product = (alerts[["product_type", "product_group"]].drop_duplicates()
               .sort_values("product_type").reset_index(drop=True))
    product.insert(0, "product_type_id", range(1, len(product) + 1))
    product.to_sql("product_type", con, if_exists="append", index=False)

    risk = pd.DataFrame({"risk_type": sorted(risk_types["risk_type"].unique())})
    risk.insert(0, "risk_type_id", range(1, len(risk) + 1))
    risk.to_sql("risk_type", con, if_exists="append", index=False)

    subst = (substances[["substance", "abbreviation", "agent_type", "substance_group", "cas_number"]]
             .drop_duplicates("substance").sort_values("substance").reset_index(drop=True))
    subst.insert(0, "substance_id", range(1, len(subst) + 1))
    subst.pipe(_none).to_sql("substance", con, if_exists="append", index=False)

    # Fact table
    a = alerts.merge(product[["product_type_id", "product_type"]], on="product_type", how="left")
    fact = pd.DataFrame({
        "alert_number": a["alert_number"], "case_id": a["case_id"], "case_url": a["case_url"],
        "alert_prefix": a["alert_prefix"], "alert_number_year": a["alert_number_year"],
        "publication_date": _iso(a["publication_date"]), "weekly_report": a["weekly_report"],
        "first_measure_date": _iso(a["first_measure_date"]),
        "alert_level": a["alert_level"], "user_type": a["user_type"],
        "notifying_country": a["notifying_country"], "origin_country": a["origin_country"],
        "origin_same_as_notifier": a["origin_same_as_notifier"].astype(int),
        "product_type_id": a["product_type_id"], "product_name": a["product_name"],
        "brand": a["brand"], "brand_raw": a["brand_raw"], "counterfeit": a["counterfeit"],
        "risk_type_combined": a["risk_type"], "risk_description": a["risk_description"],
        "legal_provision": a["legal_provision"],
        "alert_states_prohibited": a["alert_states_prohibited"].astype(int),
        "undeclared_ingredient": a["undeclared_ingredient"].astype(int),
        "has_measured_value": a["has_measured_value"].astype(int),
        "based_on_ingredient_list": a["based_on_ingredient_list"].astype(int),
        "chemical_substance_count": a["chemical_substance_count"],
        "primary_substance": a["primary_substance"],
        "barcode": a["barcode"], "batch_number": a["batch_number"],
        "source_file": a["source_file"], "source_row": a["source_row"],
    })
    fact.pipe(_none).to_sql("alert", con, if_exists="append", index=False)

    # Bridges
    rt = risk_types.merge(risk, on="risk_type")[["alert_number", "risk_type_id", "is_primary"]]
    rt.assign(is_primary=rt["is_primary"].astype(int)).to_sql("alert_risk_type", con, if_exists="append", index=False)

    sb = substances.merge(subst[["substance_id", "substance"]], on="substance")
    sb = sb[["alert_number", "substance_id", "mention_order", "is_primary", "matched_text", "method", "confidence"]]
    sb.assign(is_primary=sb["is_primary"].astype(int)).to_sql("alert_substance", con, if_exists="append", index=False)

    ms = measures.copy()
    ms["entry_into_force_date"] = _iso(ms["entry_into_force_date"])
    ms = ms.drop(columns="parsed_ok")
    ms.insert(0, "measure_id", range(1, len(ms) + 1))
    ms.pipe(_none).to_sql("alert_measure", con, if_exists="append", index=False)

    also_found[["alert_number", "country"]].drop_duplicates().to_sql("alert_also_found", con, if_exists="append", index=False)
    candidates.to_sql("substance_candidate", con, if_exists="append", index=False)

    raw_cols = ["source_file", "source_row"] + EXPECTED_COLUMNS
    raw_db = raw[raw_cols].copy()
    raw_db.columns = [
        "source_file", "source_row", "type_of_alert", "type", "alert_number", "alert_submitted_by",
        "country_of_origin", "counterfeit", "risk_type", "risk_legal_provision", "product", "name",
        "description", "brand", "category", "model", "oecd_portal_category", "risk",
        "compulsory_measures", "voluntary_measures", "also_found_in", "company_recall_page",
        "url_of_case", "barcode", "batch_number", "packaging_description", "online_trader",
    ]
    raw_db.pipe(_none).to_sql("raw_export", con, if_exists="append", index=False)

    con.commit()
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for (t,) in
              con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}
    fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
    con.close()
    if fk_errors:
        raise RuntimeError(f"Foreign key violations: {fk_errors[:5]}")
    return counts
