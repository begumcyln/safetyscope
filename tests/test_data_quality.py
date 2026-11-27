"""Automated data-quality tests on the processed dataset.

These tests check structural rules (unique keys, valid IDs, referential
integrity, reconciliation with the raw export). They do not hard-code
analytical results, except the owner's Excel checkpoints, which are
independent validation targets for this specific export.
"""

import hashlib
import sqlite3

import pandas as pd

from safetyscope import config as C
from safetyscope.extract import read_export

ORIGINAL_SHA256 = "aca3905863a34ea5622a134accd2954ad7b15be98647a68046c84e1e33c6cea1"


def test_original_export_unchanged():
    assert hashlib.sha256(C.RAW_EXPORT.read_bytes()).hexdigest() == ORIGINAL_SHA256


def test_row_count_reconciles_with_raw(alerts):
    raw = read_export(C.RAW_EXPORT)
    assert len(alerts) == len(raw)
    assert set(alerts["alert_number"]) == set(raw["Alert number"])


def test_alert_number_unique_and_valid(alerts):
    assert alerts["alert_number"].is_unique
    assert alerts["alert_number_valid"].all()
    assert alerts["alert_number"].str.match(r"^[A-Z0-9]+/\d{5}/\d{2}$").all()


def test_case_url_and_id(alerts):
    assert alerts["case_url"].str.startswith("https://ec.europa.eu/safety-gate-alerts/").all()
    assert alerts["case_id"].notna().all() and alerts["case_id"].is_unique


def test_required_fields_present(alerts):
    for col in ["alert_level", "notifying_country", "origin_country", "product_type", "risk_type", "risk_description"]:
        assert alerts[col].notna().all(), col


def test_raw_values_preserved(alerts):
    raw = read_export(C.RAW_EXPORT).set_index("Alert number")
    a = alerts.set_index("alert_number")
    for raw_col, col in [("Product", "product_raw"), ("Alert submitted by", "notifying_country_raw"),
                         ("Country of origin", "origin_country_raw"), ("Risk", "risk_description_raw")]:
        assert raw[raw_col].fillna("").equals(a.loc[raw.index, col].fillna("")), col


def test_no_leading_trailing_whitespace(alerts):
    for col in ["product_type", "brand", "notifying_country", "origin_country", "risk_type", "legal_provision"]:
        vals = alerts[col].dropna()
        assert (vals == vals.str.strip()).all(), col
        assert not vals.str.contains("  ").any(), col


def test_excel_checkpoints(alerts):
    assert len(alerts) == 1714
    assert (alerts["risk_type"] == "Chemical").sum() == 1683
    assert (alerts["risk_type"] == "Microbiological").sum() == 23
    nc = alerts["notifying_country"].value_counts()
    assert nc["Italy"] == 1129 and nc["Czechia"] == 214 and nc["Hungary"] == 161


def test_bridge_tables_reference_alerts(alerts, processed):
    ids = set(alerts["alert_number"])
    for name, df in processed.items():
        assert set(df["alert_number"]) <= ids, name


def test_every_alert_has_risk_type_and_measure(alerts, processed):
    ids = set(alerts["alert_number"])
    assert set(processed["alert_risk_types"]["alert_number"]) == ids
    assert set(processed["alert_measures"]["alert_number"]) == ids


def test_risk_type_bridge_matches_combined_label(alerts, processed):
    rebuilt = processed["alert_risk_types"].groupby("alert_number")["risk_type"].apply(", ".join)
    original = alerts.set_index("alert_number")["risk_type"]
    assert rebuilt.loc[original.index].equals(original)


def test_measures_parsed(processed):
    m = processed["alert_measures"]
    assert m["parsed_ok"].all()
    assert m["measure_kind"].isin(["compulsory", "voluntary"]).all()
    assert m["measure_group"].notna().all()
    dated = pd.to_datetime(m["entry_into_force_date"], errors="coerce")
    # Every measure either has a parsed date or the literal source value 'Unknown'
    assert (dated.notna() | m["entry_into_force_raw"].eq("Unknown")).all()


def test_substance_mentions_one_per_alert_substance(processed):
    s = processed["alert_substances"]
    assert not s.duplicated(["alert_number", "substance"]).any()
    assert s["confidence"].isin(["confirmed", "uncertain"]).all()


def test_dates_are_consistent(alerts):
    report = pd.to_datetime(alerts["weekly_report_date"], errors="coerce")
    assert report.notna().all(), "every alert should be matched to an official weekly report"
    assert (report.dt.day_of_week == 4).all(), "weekly reports are published on Fridays"
    # No alert appears in a weekly report dated before its alert-number year
    assert (report.dt.year >= alerts["alert_number_year"]).all()


def test_database_counts_match_csv(alerts, processed):
    con = sqlite3.connect(C.DB_PATH)
    try:
        assert con.execute("SELECT COUNT(*) FROM alert").fetchone()[0] == len(alerts)
        assert con.execute("SELECT COUNT(*) FROM alert_substance").fetchone()[0] == len(processed["alert_substances"])
        assert con.execute("SELECT COUNT(*) FROM alert_measure").fetchone()[0] == len(processed["alert_measures"])
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
        # Joining a bridge table must not change the distinct alert count
        n = con.execute("SELECT COUNT(DISTINCT a.alert_number) FROM alert a JOIN alert_measure m USING(alert_number)").fetchone()[0]
        assert n == len(alerts)
    finally:
        con.close()
