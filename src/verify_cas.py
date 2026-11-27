"""Cross-check the CAS numbers in the substance dictionary against PubChem.

The Safety Gate texts contain no CAS numbers. The dictionary's CAS numbers are
reference data added by the project (drafted with AI assistance). This script
checks each one independently: it asks PubChem (public NIH service, no key)
for the synonyms of the substance name and checks whether the CAS number is
among them.

Usage:
    python src/verify_cas.py

Writes data/reference/cas_verification.csv. Result values:
    verified       - CAS number found among PubChem synonyms for the name
    not_found      - PubChem knows the name but does not list this CAS number
    name_unknown   - PubChem could not resolve the name
    no_cas         - no CAS number in the dictionary (e.g. colorants, microbes)
"""

from __future__ import annotations

import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import requests  # noqa: E402

from safetyscope import config as C  # noqa: E402
from safetyscope.substances import SUBSTANCES  # noqa: E402

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{}/synonyms/JSON"

# PubChem lookup name where the display name is not a good query
LOOKUP_NAME = {
    "Mequinol (p-hydroxyanisole)": "mequinol",
    "Carbon black (nano)": "carbon black",
    "Limonene": "d-limonene",
    # "hexyl cinnamal" resolves to PubChem CID 1715135, whose synonyms do not
    # list 101-86-0; "alpha-hexylcinnamaldehyde" resolves to CID 1550884,
    # which does (checked 2026-11-27).
    "Hexyl cinnamal": "alpha-hexylcinnamaldehyde",
}


def synonyms(name: str) -> list[str] | None:
    url = PUBCHEM.format(urllib.parse.quote(name))
    r = requests.get(url, timeout=30, headers={"User-Agent": "SafetyScope/1.0 (portfolio research)"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    info = r.json()["InformationList"]["Information"]
    return [s for entry in info for s in entry.get("Synonym", [])]


def main() -> None:
    rows = []
    for name, abbr, kind, _group, _patterns, cas in SUBSTANCES:
        if kind != "chemical":
            continue
        if not cas:
            rows.append({"substance": name, "cas_number": None, "pubchem_query": None, "result": "no_cas"})
            continue
        query = LOOKUP_NAME.get(name, name)
        try:
            syn = synonyms(query)
            result = "name_unknown" if syn is None else ("verified" if cas in syn else "not_found")
        except Exception as exc:  # network problems are recorded, not hidden
            result = f"error: {exc}"
        rows.append({"substance": name, "cas_number": cas, "pubchem_query": query, "result": result})
        time.sleep(0.3)  # PubChem asks for <= 5 requests per second
    df = pd.DataFrame(rows)
    df["checked_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = C.REFERENCE_DIR / "cas_verification.csv"
    df.to_csv(out, index=False)
    print(df["result"].value_counts().to_string())
    print(df[~df["result"].isin(["verified", "no_cas"])].to_string())


if __name__ == "__main__":
    main()
