# Decision Log

| # | Date | Decision | Reason | Alternatives considered |
|---|---|---|---|---|
| D1 | 2026-11-27 | Use a Python 3.12 virtual environment (`uv venv`), not the system Python 3.15 | 3.15 is too new for reliable package wheels | System Python; conda |
| D2 | 2026-11-27 | Never modify the original export; verify it with a SHA-256 test | Reproducibility and audit trail | Clean in Excel |
| D3 | 2026-11-27 | Read every cell as text; header row = row 2 | Keeps leading zeros in barcodes; row 1 is a merged title | Default type inference |
| D4 | 2026-11-27 | Keep `*_raw` columns next to every cleaned column | Changes must be traceable | Overwrite values |
| D5 | 2026-11-27 | Keep `Unknown` origin as a category; never impute brands or names | Imputation would fabricate data | Drop or fill missing |
| D6 | 2026-11-27 | No rows removed as duplicates (0 exact duplicates; 37 near-duplicates kept) | Separate notifications of similar products are legitimate | Fuzzy de-duplication |
| D7 | 2026-11-27 | Enrich with the official Safety Gate XML weekly reports | The export has no date column; XML is the official, public, key-free source | Scraping the portal (rejected) |
| D8 | 2026-11-27 | Use the **weekly report date** as the time axis | Exists for all 1,714 alerts; XML `publicationDate` is sometimes up to 375 days later than the report | Alert-number year; publicationDate; measure date |
| D9 | 2026-11-27 | Product groups defined by explicit keyword rules (13 groups), exported for review | Transparent and reproducible | Manual mapping in Excel; ML clustering |
| D10 | 2026-11-27 | Brand matching only ignores case, accents and punctuation | Avoids merging different brands | Fuzzy string matching |
| D11 | 2026-11-27 | Rule-based dictionary + regex as the primary substance extractor | Interpretable, exact on this domain, auditable | Pretrained NER as primary |
| D12 | 2026-11-27 | Exclude the verb "lead to" from the metal *lead* with a negative look-ahead | 14 false positives otherwise | Manual review of each case |
| D13 | 2026-11-27 | Evaluate on 60 distinct risk texts with AI-produced labels, clearly labelled, plus an owner review workbook | No human annotator available; honesty about label provenance | Unlabelled evaluation; claiming accuracy |
| D14 | 2026-11-27 | Compare with `OpenMed-NER-ChemicalDetect-PubMed-109M` (Apache-2.0), pinned revision | Small, permissively licensed chemical NER | Larger models (more RAM) |
| D15 | 2026-11-27 | Cache model predictions; load the model only with `--rerun-model` | RAM pressure on the development Mac (peak ~1 GB → ~130 MB) | Re-run each time |
| D16 | 2026-11-27 | CAS numbers cross-checked against PubChem synonyms (50/50 verified) | CAS numbers were drafted with AI help and must be checked | Trust the dictionary |
| D17 | 2026-11-27 | SQLite star schema with bridge tables; `COUNT(DISTINCT alert_number)` rule | Multivalued fields without double counting | One wide table |
| D18 | 2026-11-27 | Regulatory statements only from EUR-Lex (BMHCA, TPO) or attributed to the alert text | Avoid unsupported legal claims | Summaries from memory |
| D19 | 2026-11-27 | Streamlit pages as separate view files sharing filters via `session_state` | Makes every page testable with `AppTest` | Single-file app |
| D20 | 2026-11-27 | Power BI: browser route (Excel upload + web modeling) as primary on macOS; hand-authored PBIP as untested fallback, schema-validated | Power BI Desktop is Windows-only | Claiming a working PBIP |
| D21 | 2026-11-27 | API updates go to `data/incoming/` in export layout; default start = export download date | Keeps the analysed scope unchanged unless new reports appear; one pipeline for both sources | Merge directly into processed data |
| D22 | 2026-11-27 | Commits authored with the owner's GitHub noreply address (after an interim placeholder) | Attributes the work on GitHub without publishing a personal e-mail | Use the account e-mail |
| D23 | 2026-11-27 | MIT licence for code, separate `DATA_LICENSE.md` for data | Code and data have different owners and terms | Single licence |
| D24 | 2026-11-27 | Validate the PBIP on a separate Windows computer using a minimal ZIP (project + CSVs, fixed default `DataFolder` path) instead of transferring the repository | Power BI Desktop is Windows-only; Power Query cannot use paths relative to the project file | Browser-only route; transferring the whole repository |
| D25 | 2026-11-27 | Commit the Desktop-saved `SafetyScope.pbix` unchanged (byte-identical to the tested file) | Recruiters can open the report without rebuilding it; editing a tested binary would invalidate the test | Publish only the PBIP source |
