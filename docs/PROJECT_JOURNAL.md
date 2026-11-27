# Project Journal

**AI-assistance statement.** The code, analysis and documentation in this repository were produced by an AI coding
assistant (Claude, in Claude Code) working in the project owner's environment, following the owner's written brief
and review. The owner supplied the dataset, performed the original manual Excel analysis (Excel Table, four
PivotTables, one PivotChart) and the preliminary checkpoints, and decides on publication. Reference labels in the
NLP evaluation were produced by the AI and await the owner's review. All work was done on 27 November 2026.

---

### Stage A — Data profiling and exploratory analysis
- **Objective / relevance:** understand the data before trusting any number — the first step of every BI or QA task.
- **Tools:** Python, pandas, openpyxl.
- **Actions:** inspected both workbooks; read the PivotTables' cached values programmatically; profiled 25 columns
  (types, missing values, distinct values, duplicates, alert-ID pattern, multivalued fields).
- **Key concepts:** header row detection, data profiling, reconciliation.
- **Problems → solutions:** row 1 is a merged title → read with `header=1`. One PivotTable label differed
  (`Shower gel` 38 vs 37) → Excel groups text case-insensitively, pandas does not.
- **Results:** all six Excel checkpoints reproduced exactly (1,714 / 1,683 / 23 / 1,129 / 214 / 161). The export has
  **no date column**; alert numbers carry years 20, 24 and 25.
- **Limitations:** the portal's on-screen result count was not recorded at download time.

### Stage B — ETL pipeline and date investigation
- **Objective:** a reproducible, documented cleaning process.
- **Tools:** pandas, regex, official Safety Gate XML (weekly reports 2020, 2024–2026).
- **Actions:** whitespace/encoding normalisation (1,694 cells), product standardisation (231 → 180 types),
  country mapping with ISO codes, conservative brand matching (18 brands merged), measure parsing (2,027 measures,
  0 failures), bridge tables, XML enrichment (1,714 of 1,714 alerts matched to a weekly report).
- **Problems → solutions:** "Which date is the 2025 filter?" → reconciliation against the XML: *weekly report in
  2025 or publicationDate in 2025* reproduces all 1,714 rows (hypothesis; two portal alerts fitting the rule are
  absent from the export). `publicationDate` can be up to 375 days after the weekly report → dates kept separate.
- **Results:** `data/processed/`, `reports/cleaning_report.md`, `reports/date_investigation.md`.
- **Limitations:** the meaning of the alert-number suffix and of `publicationDate` is inferred, not documented.

### Stage C — Chemical substance extraction (NLP)
- **Objective:** turn free-text risk descriptions into a substance dimension.
- **Tools:** regex dictionary (67 substances/agents), PubChem, Hugging Face Transformers (comparison only).
- **Actions:** alias patterns (e.g. three spellings of BMHCA), typo handling, `lead`-vs-"lead to" rule, uncertain
  candidates, CAS cross-check (50/50), 60-text evaluation sample, model comparison, owner review workbook.
- **Results:** 1,822 mentions in 1,709 alerts; 5 alerts name no substance (e.g. SPF too low). Rules agree with the
  AI reference labels on all 60 texts (an internal-consistency check, not validated accuracy). The pretrained model
  (precision 0.89, recall 0.99 on chemicals) found no new substance; its extra outputs were class words such as
  "corticosteroid", and it never tagged *lead*.
- **Limitations:** labels not yet human-verified; dictionary built on the evaluated data.

### Stage D — SQLite data model and SQL
- **Objective:** a queryable model that answers business questions without double counting.
- **Actions:** star schema (fact `alert`, dimensions, bridges), foreign-key checks, 20 commented queries, runner
  that executes and saves every result.
- **Key concept:** joining `alert_measure` turns 1,714 alerts into 2,027 rows → `COUNT(DISTINCT)`.
- **Results:** `sql/`, `reports/sql_results.md`, `docs/DATABASE.md`.

### Stage E — Findings and executive summary
- **Results (verified):** BMHCA named in 86.8% of alerts; fragrances 44.6% of alerts; Italy 65.9% of alerts, 97.2% of
  them BMHCA, 99.5% based on ingredient lists, median 359 days from measure to report (others: 53); all 53 TPO
  alerts appeared on/after 1 Sep 2025, when Regulation (EU) 2025/877 began to apply.
- **Interpretation (hypothesis):** Italy's share is consistent with large-scale, label-based enforcement of the BMHCA
  prohibition notified in batches; the data cannot show causes or compare national compliance.
- **Problem → solution:** a draft sentence said skin-lightening products were "mostly destroyed"; checking showed
  they are mostly **rejected at the border** (32 of 55) → corrected from data.

### Stage F — Power BI
- **Constraint:** Power BI Desktop is Windows-only; development on macOS.
- **Actions:** star-schema CSVs and an Excel upload workbook for app.powerbi.com; M scripts; 17 DAX measures with
  reference values; theme; hand-authored PBIP whose 39 JSON files pass Microsoft's schemas.
- **Windows validation (project owner):** a minimal package (PBIP + CSVs + instructions) was opened in Power BI
  Desktop on a separate Windows computer, refreshed successfully, and all KPI cards matched the Python/SQL reference
  values (1,714 alerts; 86.8% BMHCA; 57 chemicals; 18 notifying countries; median 289 days; 1,292 bans). The saved
  report is `powerbi/SafetyScope.pbix`; screenshots are in `assets/screenshots/powerbi_*.jpg`.
- **Remaining limitation:** the custom theme was not applied, and some bar charts use alphabetical sorting.

### Stage G — Streamlit application
- **Actions:** six pages, global filters, case links, CSV download, provenance page; headless `AppTest` tests;
  visual check in a browser; real screenshots.
- **Problems → solutions:** one 2020 alert stretched the trend axis over five years → trend starts Dec 2024 with a
  caption; heatmap dominated by BMHCA → share of product group instead of counts.

### Stage H — API and automation
- **Findings:** the official XML download is public, key-free, updated every Friday, documented in the file itself.
- **Actions:** cached, rate-limited client with retries and a retrieval log; `update_from_api.py` adds only unseen
  Cosmetics alerts from newer reports to `data/incoming/` (dry-run: none newer than 27 Nov 2026); offline tests.
- **Fallback:** new portal Excel exports can be dropped into `data/incoming/`.

### Stages I–J — Documentation and publication
- README, data dictionary, decision log, licences, learning guide; repository checked for secrets and size.
- **Environment note:** the development Mac came under memory pressure; work was made sequential, the model cached,
  and servers stopped after use.
