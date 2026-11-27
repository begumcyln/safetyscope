"""SafetyScope ETL pipeline: Extract -> Transform -> Load.

Usage:
    python src/pipeline.py

Steps
1. Extract  - read the original Safety Gate Excel export (unchanged) plus any
              newer exports placed in data/incoming/.
2. Transform- clean, standardise, split multivalued fields, parse measures,
              extract substances, enrich with publication dates from the
              cached official XML weekly reports (if downloaded).
3. Load     - write analysis-ready CSVs to data/processed/, a SQLite database,
              Power BI CSVs, and a machine-readable run summary.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from safetyscope import config as C  # noqa: E402
from safetyscope import transform as T  # noqa: E402
from safetyscope.database import build_database  # noqa: E402
from safetyscope.extract import file_sha256, read_export  # noqa: E402
from safetyscope.safety_gate_api import load_cached_reports  # noqa: E402
from safetyscope.substances import dictionary_table  # noqa: E402


def extract_all() -> tuple[pd.DataFrame, list[dict], pd.DataFrame]:
    """Read the original export and any incoming exports; de-duplicate by alert number."""
    files = [C.RAW_EXPORT] + sorted(C.INCOMING_DIR.glob("*.xlsx"))
    frames, provenance = [], []
    for order, path in enumerate(files):
        df = read_export(path)
        df["source_order"] = order
        frames.append(df)
        provenance.append({"file": path.name, "sha256": file_sha256(path), "rows": len(df)})
    combined = pd.concat(frames, ignore_index=True)
    # Duplicate prevention: if the same alert appears in several exports, keep
    # the record from the most recently added export (latest information).
    dup_mask = combined.duplicated("Alert number", keep=False)
    duplicates = combined[dup_mask].copy()
    combined = combined.sort_values("source_order").drop_duplicates("Alert number", keep="last")
    return combined.drop(columns="source_order").sort_values(["source_file", "source_row"]).reset_index(drop=True), provenance, duplicates


def main() -> dict:
    run_started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    C.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    C.INCOMING_DIR.mkdir(parents=True, exist_ok=True)

    raw, provenance, cross_file_dups = extract_all()
    alerts = T.build_alerts(raw)

    xml = load_cached_reports()
    alerts = T.add_xml_enrichment(alerts, xml)

    risk_types = T.build_risk_types(alerts)
    measures = T.build_measures(alerts)
    also_found = T.build_also_found(alerts)
    substances, candidates = T.build_substances(alerts)

    # Per-alert summary columns derived from the bridge tables
    first_measure = measures.groupby("alert_number")["entry_into_force_date"].min().rename("first_measure_date")
    alerts = alerts.merge(first_measure, on="alert_number", how="left")
    n_subs = substances[substances.agent_type == "chemical"].groupby("alert_number").size().rename("chemical_substance_count")
    alerts = alerts.merge(n_subs, on="alert_number", how="left")
    alerts["chemical_substance_count"] = alerts["chemical_substance_count"].fillna(0).astype(int)
    primary = substances[substances.is_primary].set_index("alert_number")["substance"].rename("primary_substance")
    alerts = alerts.merge(primary, on="alert_number", how="left")

    # ---- Load: CSV outputs -------------------------------------------------
    out = C.PROCESSED_DIR
    alerts.to_csv(out / "alerts_clean.csv", index=False)
    risk_types.to_csv(out / "alert_risk_types.csv", index=False)
    measures.to_csv(out / "alert_measures.csv", index=False)
    also_found.to_csv(out / "alert_also_found.csv", index=False)
    substances.to_csv(out / "alert_substances.csv", index=False)
    candidates.to_csv(out / "substance_candidates_uncertain.csv", index=False)
    pd.DataFrame(dictionary_table()).to_csv(C.REFERENCE_DIR / "substance_dictionary.csv", index=False)
    if not xml.empty:
        xml_cosmetics = xml[xml["category"].eq("Cosmetics")]
        xml_cosmetics.to_csv(out / "xml_cosmetics_alerts.csv", index=False)

    # Mapping tables exported for review
    (alerts[["product_raw", "product_type", "product_group"]].value_counts().reset_index(name="alerts")
     .sort_values(["product_group", "product_type"]).to_csv(C.REFERENCE_DIR / "product_mapping.csv", index=False))
    (alerts[["brand_raw", "brand_key", "brand"]].value_counts(dropna=False).reset_index(name="alerts")
     .sort_values("brand_key").to_csv(C.REFERENCE_DIR / "brand_mapping.csv", index=False))

    db_counts = build_database(alerts, risk_types, measures, also_found, substances, candidates, raw)

    summary = {
        "run_started_utc": run_started,
        "source_files": provenance,
        "cross_file_duplicates_removed": int(len(cross_file_dups) - cross_file_dups["Alert number"].nunique()) if len(cross_file_dups) else 0,
        "alerts": len(alerts),
        "risk_type_rows": len(risk_types),
        "measure_rows": len(measures),
        "substance_mentions": len(substances),
        "uncertain_candidates": len(candidates),
        "xml_reports_cached": int(xml["report_reference"].nunique()) if not xml.empty else 0,
        "alerts_matched_in_xml": int(alerts["xml_matched"].sum()),
        "database_tables": db_counts,
    }
    (out / "pipeline_run_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
