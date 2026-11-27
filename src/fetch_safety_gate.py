"""Command-line entry point: download Safety Gate weekly reports via the official XML API.

Usage:
    python src/fetch_safety_gate.py --years 2025 2026
    python src/fetch_safety_gate.py --years 2026 --force   # re-download (corrections)

Downloaded reports are cached in data/external/weekly_reports/. Run
`python src/pipeline.py` afterwards to rebuild the processed dataset.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from safetyscope.safety_gate_api import download_years, setup_logging  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--years", type=int, nargs="+", required=True, help="Publication years of weekly reports")
    parser.add_argument("--force", action="store_true", help="Re-download reports already cached")
    args = parser.parse_args()
    setup_logging()
    paths = download_years(args.years, force=args.force)
    print(f"{len(paths)} weekly report files available in cache for years {args.years}.")


if __name__ == "__main__":
    main()
