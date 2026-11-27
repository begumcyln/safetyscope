# Learning Guide

A plain-language explanation of every technique in SafetyScope, so you can discuss the project without reading the
code. Each section answers: *what is it, where is it in this project, why does it matter.*

## 1. The business problem in one paragraph
EU authorities report unsafe products to **Safety Gate**. Each report is an *alert*. Companies that sell cosmetics
want to know which ingredients and products trigger alerts and what happens afterwards (bans, recalls). The raw
export is messy: substances hide inside sentences, some cells hold several values, and there is no date column.
SafetyScope turns it into clean tables, a database, an app and dashboards — reproducibly.

## 2. Core concepts

**ETL (Extract, Transform, Load).** *Extract* = read the Excel export exactly as downloaded (`src/safetyscope/extract.py`).
*Transform* = clean and restructure it (`transform.py`, `standardize.py`, `measures.py`, `substances.py`).
*Load* = save the result as CSV files and a SQLite database (`database.py`). One command runs everything:
`python src/pipeline.py`. Why it matters: anyone can repeat the work and get the same numbers.

**pandas.** A Python library for tables ("DataFrames"). Think of Excel, but every step is written down as code.
Example: `alerts["notifying_country"].value_counts()` is a PivotTable that counts alerts per country.

**Data profiling.** Checking a dataset before using it: how many rows, which columns are empty, are there
duplicates, are categories spelt consistently. Result here: 1,714 rows, 25 columns, no duplicate alert numbers,
231 product spellings that collapse to 180 product types.

**Data cleaning without losing the original.** Every cleaned column (e.g. `product_type`) sits next to the original
(`product_raw`). Nothing is guessed: a missing brand stays missing.

**Multivalued fields and bridge tables.** One alert can name two substances. Instead of squeezing both into one cell,
a *bridge table* (`alert_substances`) holds one row per alert–substance pair. Counting then needs care: join alerts
to measures and 1,714 alerts become 2,027 rows. Always count `DISTINCT alert_number`.

**Data model / star schema.** A central *fact* table (alerts) linked to *dimension* tables (products, substances,
countries). The same idea is used in the SQL database and in Power BI.

**SQL.** The language for asking questions of a database. Example (query q01):
`SELECT product_group, COUNT(*) FROM alert JOIN product_type ... GROUP BY product_group` = "alerts per product
group". SQLite is a database stored in one file, no server needed.

**Regular expressions (regex).** Text patterns. `\blead\b(?!\s+to\b)` means "the word *lead*, but not when followed by
*to*" — so "may lead to endocrine problems" is not mistaken for the metal lead.

**NLP and named-entity recognition (NER).** NLP = computer processing of language. NER = finding names of things
(here: chemicals) in text. Two approaches were compared: a **dictionary + regex** (transparent, built for these
texts) and a **pretrained AI model** from Hugging Face (needs no dictionary but was trained on scientific
abstracts). The dictionary was more precise here; the model tagged class words like "corticosteroid".

**Evaluation: precision and recall.** Precision = of everything the system extracted, how much was right.
Recall = of everything that should have been found, how much was found. Honest caveat: the reference labels were
written by an AI, so the perfect rule-based score shows consistency, not proven accuracy.

**API.** A way for programs to fetch data. Safety Gate publishes an XML file listing all weekly reports; the project
downloads them politely (one per second, cached, logged) to add publication dates and to check for new alerts.

**Power Query (M).** Power BI's data-preparation language. The `.pq` files tell Power BI how to load each CSV and set
column types — the ETL "extract/transform" step inside Power BI.

**DAX.** Power BI's formula language for measures. `Total Alerts = DISTINCTCOUNT(Alerts[alert_number])` counts
alerts and automatically respects slicers and filters.

**Business Intelligence (BI).** Turning data into decisions: KPIs (key numbers), dashboards, and — most important —
correct interpretation. Here: alert counts measure *enforcement activity*, not how unsafe a country's products are.

**Streamlit.** A Python library that turns a script into a web app (`app/`). Filters in the sidebar change every chart.

**Testing.** `pytest` runs 46 automatic checks: the original file is unchanged, counts reconcile, every alert has a
measure, each app page loads, Power BI files match Microsoft's schemas.

## 3. Key results you should be able to explain
- BMHCA (Lilial), prohibited in EU cosmetics since 1 March 2022 (Regulation (EU) 2021/1902), appears in 86.8% of alerts.
- Italy submitted 65.9% of alerts — almost all BMHCA, based on ingredient lists, notified in batches about a year
  after the national measure. This shows enforcement focus, not that Italian products are less safe.
- All 53 TPO alerts (nail products) came on or after 1 September 2025, when TPO's prohibition began to apply.
- The "2025" export is defined by publication, not by alert-number year — which is why `/24` and `/20` alerts appear.

## 4. Interview preparation

**Q: Walk me through the project.**
A: I took a Safety Gate export of 1,714 cosmetics alerts, validated it against my earlier Excel analysis, built a
reproducible Python pipeline to clean it, extracted chemical substances from free text, modelled it in SQL, and
delivered a Streamlit app and Power BI assets. Each step is documented and tested.

**Q: How did you make sure the numbers are right?**
A: Three ways: the Python results reproduce my Excel PivotTables exactly; automated tests check row counts, keys and
relationships; and every report number is generated by a script, never typed by hand.

**Q: What was the hardest data problem?**
A: Dates. The export had none, and alert numbers suggested different years. I matched every alert to the official
weekly reports and found that publication dates can differ from report dates by up to a year — so I documented each
date's meaning and used one consistent definition.

**Q: Why rules instead of AI for extraction?**
A: The texts are formulaic, so rules are precise and explainable — important in a regulatory context. I still
tested a pretrained model; it found nothing new and mislabelled class words, which supported the choice.

**Q: Italy has two thirds of the alerts. Are Italian products more dangerous?**
A: The data cannot say that. Without the number of inspections or products on the market there is no denominator.
The pattern — almost all BMHCA, found from ingredient lists, published in batches — points to an enforcement
campaign, which I state as a hypothesis.

**Q: How do you avoid double counting?**
A: Multivalued attributes live in bridge tables, and every count over a join uses distinct alert numbers. I even
included a query that shows the wrong and right count side by side (2,027 vs 1,714).

**Q: What would you improve?**
A: Human review of the evaluation labels, a second export to test the dictionary on unseen data, a confirmed
definition of the portal's date filter, and polishing the Power BI report (theme, sorting) now that it runs in Desktop.

**Q: How did you build a Power BI report on a Mac?**
A: Power BI Desktop is Windows-only, so the project was written as a Power BI Project — text files describing the
model and report — and checked against Microsoft's published schemas. I then opened it on a Windows computer,
refreshed it and confirmed that every KPI matched the Python and SQL results.

**Q: What was your role versus the AI assistant?**
A: I defined the problem, supplied the data and the manual Excel baseline, set the requirements and reviewed the
results. The code and documentation were generated with an AI coding assistant; this is stated in the project journal.
