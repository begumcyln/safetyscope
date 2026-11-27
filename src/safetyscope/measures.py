"""Parse the semi-structured 'Compulsory measures' and 'Voluntary measures' fields.

Each field contains one or more blocks separated by a blank line, e.g.

    Type of economic operator to whom the measure(s) were ordered: Distributor
    Category of measure(s): Ban on the marketing of the product and any accompanying measures
    Date of entry into force: 08/10/2024

One alert can therefore have several measures. We return one row per measure.
"""

from __future__ import annotations

import re

import pandas as pd

OPERATOR_RE = re.compile(r"Type of economic operator[^:]*:\s*(.+)", re.I)
CATEGORY_RE = re.compile(r"Category of measure\(s\)\s*:\s*(.+)", re.I)
DATE_RE = re.compile(r"Date of entry into force\s*:\s*(.+)", re.I)


def parse_measures(text: str | None, kind: str) -> list[dict]:
    if text is None or (isinstance(text, float) and pd.isna(text)) or not str(text).strip():
        return []
    blocks = re.split(r"\n\s*\n", str(text).replace("\r\n", "\n").strip())
    rows = []
    for block in blocks:
        operator = OPERATOR_RE.search(block)
        category = CATEGORY_RE.search(block)
        date = DATE_RE.search(block)
        raw_date = date.group(1).strip() if date else None
        parsed_date = pd.to_datetime(raw_date, format="%d/%m/%Y", errors="coerce") if raw_date else pd.NaT
        rows.append({
            "measure_kind": kind,  # "compulsory" (ordered by authority) or "voluntary" (taken by operator)
            "economic_operator": operator.group(1).strip() if operator else None,
            "measure_category": category.group(1).strip() if category else None,
            "entry_into_force_raw": raw_date,
            "entry_into_force_date": parsed_date,
            "block_text": block.strip(),
            "parsed_ok": bool(category),
        })
    return rows
