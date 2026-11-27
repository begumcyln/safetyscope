"""Central file paths and constants used throughout the project."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"
RAW_EXPORT = DATA_DIR / "search_list_20261127_notification_list.xlsx"  # never modified
EXCEL_WORKING_COPY = ROOT / "analysis" / "cosmetics_working_data.xlsx"  # owner's manual work
EXTERNAL_DIR = DATA_DIR / "external"
PROCESSED_DIR = DATA_DIR / "processed"
INCOMING_DIR = DATA_DIR / "incoming"  # drop new Safety Gate Excel exports here
REFERENCE_DIR = DATA_DIR / "reference"

REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
POWERBI_DIR = ROOT / "powerbi"
LOG_DIR = ROOT / "logs"

DB_PATH = PROCESSED_DIR / "safetyscope.db"

# The Excel export has a merged title row ("Safety Gate : the EU rapid alert
# system...") in row 1; the real column headers are in row 2.
HEADER_ROW_INDEX = 1  # zero-based, for pandas.read_excel(header=...)

EXPORT_DOWNLOAD_DATE = "2026-11-27"
