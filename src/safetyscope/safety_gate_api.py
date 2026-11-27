"""Client for the official, public Safety Gate weekly-report XML download.

Endpoints (published by the European Commission, no API key required):

* Index of all weekly reports (2005 -> present, new report every Friday):
  https://ec.europa.eu/safety-gate-alerts/api/download/weeklyReport/list/xml/en
* One weekly report (all alerts published that week, all product categories):
  the <URL> element of each <weeklyReport> entry in the index.

Design choices
--------------
* Downloaded XML files are cached on disk (data/external/weekly_reports/), so a
  report is never fetched twice. Past weekly reports can still receive
  corrections, so ``force=True`` re-downloads them.
* Requests are rate-limited (default: 1 second between calls) and retried with
  back-off. We do not bypass any access restriction; if the service refuses
  the request, the error is logged and the project keeps working from the
  local Excel export.
* Every downloaded file is recorded in a JSON-lines log with a UTC retrieval
  timestamp, so the provenance of each record can be traced.
"""

from __future__ import annotations

import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from .config import EXTERNAL_DIR, LOG_DIR

INDEX_URL = "https://ec.europa.eu/safety-gate-alerts/api/download/weeklyReport/list/xml/en"
USER_AGENT = "SafetyScope/1.0 (portfolio research project; respectful rate-limited client)"
REPORT_DIR = EXTERNAL_DIR / "weekly_reports"
INDEX_FILE = EXTERNAL_DIR / "weekly_report_index.xml"
RETRIEVAL_LOG = EXTERNAL_DIR / "retrieval_log.jsonl"

log = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(url: str, retries: int = 3, timeout: int = 90) -> bytes:
    """HTTP GET with retries and exponential back-off."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            if response.status_code in (401, 403):
                # Access refused: stop immediately, never try to work around it.
                raise PermissionError(f"Access refused ({response.status_code}) for {url}")
            response.raise_for_status()
            return response.content
        except PermissionError:
            raise
        except Exception as exc:  # network errors, 5xx, timeouts
            last_error = exc
            wait = 2 ** attempt
            log.warning("Attempt %s/%s failed for %s: %s (retrying in %ss)", attempt, retries, url, exc, wait)
            time.sleep(wait)
    raise ConnectionError(f"Giving up on {url}: {last_error}")


def _record_retrieval(kind: str, url: str, path: Path, n_bytes: int) -> None:
    RETRIEVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"retrieved_at_utc": _utc_now(), "kind": kind, "url": url, "file": str(path.name), "bytes": n_bytes}
    with RETRIEVAL_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def fetch_index(refresh: bool = True) -> pd.DataFrame:
    """Download (or read cached) list of weekly reports."""
    if refresh or not INDEX_FILE.exists():
        content = _get(INDEX_URL)
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        INDEX_FILE.write_bytes(content)
        _record_retrieval("index", INDEX_URL, INDEX_FILE, len(content))
    root = ET.parse(INDEX_FILE).getroot()
    rows = [{child.tag: (child.text or "").strip() for child in report} for report in root.findall("weeklyReport")]
    index = pd.DataFrame(rows)
    index["year"] = index["year"].astype(int)
    index["week"] = index["week"].astype(int)
    index["publicationDate"] = pd.to_datetime(index["publicationDate"], format="%d/%m/%Y")
    return index


def fetch_report(reference: str, url: str, force: bool = False, pause: float = 1.0) -> Path:
    """Download one weekly report XML into the cache (skips if already cached)."""
    path = REPORT_DIR / f"{reference}.xml"
    if path.exists() and not force:
        return path
    content = _get(url)
    ET.fromstring(content)  # validate well-formed XML before saving
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    _record_retrieval("weekly_report", url, path, len(content))
    time.sleep(pause)  # be polite to the public service
    return path


def parse_report(path: Path) -> pd.DataFrame:
    """Flatten one weekly-report XML file into one row per notification."""
    root = ET.parse(path).getroot()
    header = {
        "report_reference": path.stem,
        "report_date": (root.findtext("report_date") or "").strip(),
        "report_year": (root.findtext("report_year") or "").strip(),
        "report_week": (root.findtext("report_week") or "").strip(),
    }
    rows = []
    for notification in root.findall("notifications"):
        row = dict(header)
        for child in notification:
            if child.tag == "pictures":
                row["pictures"] = " | ".join((p.text or "").strip() for p in child)
            else:
                row[child.tag] = (child.text or "").strip()
        rows.append(row)
    return pd.DataFrame(rows)


def download_years(years: list[int], force: bool = False) -> list[Path]:
    """Download every weekly report published in the given years."""
    index = fetch_index(refresh=True)
    selected = index[index["year"].isin(years)].sort_values("publicationDate")
    paths = []
    for _, report in selected.iterrows():
        try:
            paths.append(fetch_report(report["reference"], report["URL"], force=force))
            log.info("OK %s", report["reference"])
        except PermissionError as exc:
            log.error("%s - stopping, access refused.", exc)
            break
        except Exception as exc:
            log.error("Failed %s: %s", report["reference"], exc)
    return paths


def load_cached_reports(years: list[int] | None = None) -> pd.DataFrame:
    """Parse all cached weekly reports into a single DataFrame (all categories)."""
    frames = []
    for path in sorted(REPORT_DIR.glob("Report-*.xml")):
        year = int(path.stem.split("-")[1])
        if years and year not in years:
            continue
        frames.append(parse_report(path))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_DIR / "safety_gate_api.log"), logging.StreamHandler()],
    )
