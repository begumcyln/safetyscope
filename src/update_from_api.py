"""Stage H - add newly published Safety Gate cosmetics alerts from the official XML API.

Usage:
    python src/update_from_api.py                 # reports published after the last update
    python src/update_from_api.py --since 2026-12-01
    python src/update_from_api.py --dry-run       # show what would be added, write nothing
    python src/pipeline.py                        # then rebuild the processed dataset

How it works
1. Reads the official weekly-report index and selects reports published after
   `--since` (default: the date stored in data/external/update_state.json, or
   the original export's download date on the first run).
2. Downloads only those reports (cached; rate-limited; logged with timestamps).
3. Keeps alerts with category 'Cosmetics' whose alert number is not already in
   the original export or in any file in data/incoming/ (duplicate prevention).
4. Writes them in the same layout as a portal Excel export to
   data/incoming/safety_gate_api_<date>.xlsx, so the normal pipeline picks them
   up. Fields the XML does not provide (Counterfeit, legal provision, OECD
   category, packaging, 'also found in') are left empty.

The project works without this script: new portal Excel exports can simply be
dropped into data/incoming/ instead.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from openpyxl import Workbook  # noqa: E402

from safetyscope import config as C  # noqa: E402
from safetyscope.extract import EXPECTED_COLUMNS, read_export  # noqa: E402
from safetyscope.safety_gate_api import fetch_index, fetch_report, parse_report, setup_logging  # noqa: E402

STATE_FILE = C.EXTERNAL_DIR / "update_state.json"
log = logging.getLogger("update_from_api")


def split_measures(text: str | None) -> tuple[str | None, str | None]:
    """Rebuild the export's measure layout from the XML's concatenated text.

    'Type of economic operator to whom the measure(s) were ordered' -> compulsory
    'Type of economic operator taking notified measure(s)'          -> voluntary
    """
    if not text:
        return None, None
    blocks = re.split(r"(?=Type of economic operator)", text)
    comp, vol = [], []
    for b in (b.strip() for b in blocks if b.strip()):
        b = re.sub(r"\s*(Category of measure\(s\):)", r"\n\1", b)
        b = re.sub(r"\s*(Date of entry into force:)", r"\n\1", b)
        (comp if "were ordered" in b else vol).append(b)
    return ("\n\n".join(comp) or None), ("\n\n".join(vol) or None)


XML_FIELDS = ["level", "type", "caseNumber", "notifyingCountry", "countryOfOrigin", "riskType", "product", "name",
              "description", "brand", "category", "type_numberOfModel", "danger", "measures", "URLrecall",
              "reference", "barcode", "batchNumber", "onlineTrader"]


def to_export_layout(x: pd.DataFrame) -> pd.DataFrame:
    x = x.reindex(columns=XML_FIELDS)  # optional tags may be absent in a report
    x = x.astype(object).where(x.notna(), None)
    rows = []
    for r in x.itertuples():
        comp, vol = split_measures(getattr(r, "measures", None))
        rows.append({
            "Type of alert": r.level, "Type": r.type, "Alert number": r.caseNumber,
            "Alert submitted by": r.notifyingCountry, "Country of origin": r.countryOfOrigin or "Unknown",
            "Counterfeit": None, "Risk type": r.riskType, "Risk legal provision": None,
            "Product": r.product, "Name": r.name or None, "Description": r.description or None,
            "Brand": r.brand or None, "Category": r.category, "Type / number of model": r.type_numberOfModel or None,
            "OECD Portal category": None, "Risk": r.danger, "Compulsory measures": comp, "Voluntary measures": vol,
            "Products were found and measures were taken also in": None, "Company recall page": r.URLrecall or None,
            "URL of Case": r.reference, "Barcode": r.barcode or None, "Batch number": r.batchNumber or None,
            "Packaging description": None, "Online trader": r.onlineTrader or None,
        })
    return pd.DataFrame(rows, columns=EXPECTED_COLUMNS)


def write_export_like(df: pd.DataFrame, path: Path) -> None:
    """Same layout as a portal export: title row 1, headers row 2, data from row 3."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Weekly Reports"
    ws.append(["Safety Gate : the EU rapid alert system for dangerous non-food products (via official XML API)"])
    ws.append(EXPECTED_COLUMNS)
    for row in df.itertuples(index=False):
        ws.append([None if (v is None or (isinstance(v, float) and pd.isna(v))) else v for v in row])
    wb.save(path)


def known_alert_numbers() -> set[str]:
    known = set(read_export(C.RAW_EXPORT)["Alert number"])
    for f in C.INCOMING_DIR.glob("*.xlsx"):
        known |= set(read_export(f)["Alert number"])
    return known


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", help="ISO date; only weekly reports published after this date")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    setup_logging()

    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    since = pd.Timestamp(args.since or state.get("last_report_date") or C.EXPORT_DOWNLOAD_DATE)
    try:
        index = fetch_index(refresh=True)
    except Exception as exc:  # the project must keep working without API access
        log.error("Could not reach the Safety Gate XML API (%s). Use data/incoming/ for Excel exports instead.", exc)
        return
    todo = index[index["publicationDate"] > since].sort_values("publicationDate")
    log.info("%s weekly reports published after %s", len(todo), since.date())

    frames = []
    for r in todo.itertuples():
        try:
            frames.append(parse_report(fetch_report(r.reference, r.URL)))
        except Exception as exc:
            log.error("Skipping %s: %s", r.reference, exc)
    if not frames:
        print(f"No weekly reports newer than {since.date()} - dataset is up to date.")
        return
    xml = pd.concat(frames, ignore_index=True)
    cosmetics = xml[xml["category"].eq("Cosmetics")].drop_duplicates("caseNumber")
    known = known_alert_numbers()
    new = cosmetics[~cosmetics["caseNumber"].isin(known)]
    log.info("Reports: %s | cosmetics alerts: %s | already known: %s | new: %s",
             xml["report_reference"].nunique(), len(cosmetics), len(cosmetics) - len(new), len(new))

    if args.dry_run:
        print(new[["caseNumber", "report_reference", "notifyingCountry", "product"]].to_string(index=False))
        return
    if len(new):
        C.INCOMING_DIR.mkdir(parents=True, exist_ok=True)
        out = C.INCOMING_DIR / f"safety_gate_api_{date.today():%Y%m%d}.xlsx"
        write_export_like(to_export_layout(new), out)
        log.info("Wrote %s new alerts to %s", len(new), out)
    latest = todo["publicationDate"].max()
    STATE_FILE.write_text(json.dumps({"last_report_date": str(latest.date()),
                                      "updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                      "new_alerts_last_run": int(len(new))}, indent=2))
    print(f"{len(new)} new cosmetics alerts. Run `python src/pipeline.py` to rebuild the dataset.")


if __name__ == "__main__":
    main()
