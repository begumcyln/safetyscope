"""Extract step: read a Safety Gate Excel export exactly as downloaded.

The export has one worksheet ("Weekly Reports"). Row 1 is a merged title cell,
row 2 contains the column headers and data starts in row 3. All cells are read
as text (dtype=str) so that barcodes, batch numbers and alert numbers keep
their leading zeros and are never converted to numbers or dates.
"""

from __future__ import annotations

import hashlib
import warnings
from pathlib import Path

import pandas as pd

from .config import HEADER_ROW_INDEX

EXPECTED_COLUMNS = [
    "Type of alert", "Type", "Alert number", "Alert submitted by", "Country of origin",
    "Counterfeit", "Risk type", "Risk legal provision", "Product", "Name", "Description",
    "Brand", "Category", "Type / number of model", "OECD Portal category", "Risk",
    "Compulsory measures", "Voluntary measures",
    "Products were found and measures were taken also in", "Company recall page",
    "URL of Case", "Barcode", "Batch number", "Packaging description", "Online trader",
]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_export(path: Path) -> pd.DataFrame:
    """Read one Safety Gate Excel export and check that its layout is as expected."""
    with warnings.catch_warnings():
        # The export has no default style; openpyxl warns but reads it correctly.
        warnings.simplefilter("ignore", UserWarning)
        df = pd.read_excel(path, header=HEADER_ROW_INDEX, dtype=str)
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: unexpected export layout, missing columns {missing}")
    df = df[EXPECTED_COLUMNS].copy()
    df = df.dropna(how="all")  # guard against trailing empty rows
    df.insert(0, "source_row", range(HEADER_ROW_INDEX + 2, HEADER_ROW_INDEX + 2 + len(df)))  # Excel row number
    df.insert(1, "source_file", Path(path).name)
    return df
