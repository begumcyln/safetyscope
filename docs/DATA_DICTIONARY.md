# Data Dictionary

Unit of analysis: **one Safety Gate alert** (a notification by a national authority). `*_raw` columns hold the
original export value unchanged; the column without `_raw` is the cleaned version.

## 1. Source export (`data/search_list_20261127_notification_list.xlsx`)

Sheet `Weekly Reports`, merged title in row 1, headers in row 2, 1,714 data rows, 25 columns, all text.

| Export column | Meaning | Cleaned column(s) |
|---|---|---|
| Type of alert | Risk level (`Serious risk`, `Other risk levels`, `Other types of alerts`) | `alert_level` |
| Type | `Consumer` or `Professional` product | `user_type` |
| Alert number | Safety Gate case number `PREFIX/NNNNN/YY` | `alert_number`, `alert_prefix`, `alert_sequence`, `alert_number_year` |
| Alert submitted by | Notifying country (authority that sent the alert) | `notifying_country(_raw)`, `notifying_country_iso2` |
| Country of origin | Declared origin of the product; `Unknown` = not established | `origin_country(_raw)`, `origin_country_iso2`, `origin_known`, `origin_is_eu` |
| Counterfeit | `Yes` / `No` / `Unknown` | `counterfeit` |
| Risk type | Hazard category; may hold several values, comma-separated | `risk_type(_raw)`, bridge `alert_risk_types` |
| Risk legal provision | Legislation not complied with | `legal_provision(_raw)` |
| Product | Product type (free text, inconsistent spelling) | `product_raw`, `product_type`, `product_group` |
| Name | Product (trade) name | `product_name(_raw)` |
| Description | Physical description | `description` |
| Brand | Brand as written by the authority | `brand_raw`, `brand`, `brand_key` |
| Category | Safety Gate product category (always `Cosmetics` here) | `category` |
| Type / number of model | Model reference | `model` |
| OECD Portal category | OECD product classification | `oecd_category` |
| Risk | Free-text risk description (source of substance extraction) | `risk_description(_raw)` |
| Compulsory measures | Measures ordered by authorities (multi-line blocks) | `compulsory_measures_raw`, table `alert_measures` |
| Voluntary measures | Measures taken by economic operators | `voluntary_measures_raw`, table `alert_measures` |
| Products were found and measures were taken also in | Other countries with follow-up measures | `also_found_in(_raw)`, table `alert_also_found` |
| Company recall page | URL of the company's recall notice | `company_recall_page` |
| URL of Case | Link to the alert on the Safety Gate portal | `case_url`, `case_id` |
| Barcode, Batch number, Packaging description, Online trader | Identification details (`Online trader` is empty in this export) | same names |

## 2. `data/processed/alerts_clean.csv` — derived columns

| Column | Type | Definition |
|---|---|---|
| source_file, source_row | text, int | File and Excel row the record came from |
| alert_number_valid | bool | Alert number matches `PREFIX/NNNNN/YY` |
| alert_number_year | int | 2000 + two-digit suffix. **Not** the publication year |
| case_id | text | Numeric id in `case_url` |
| product_type | text | Standardised `Product` (case, spacing and spelling variants merged) |
| product_group | text | Project-defined grouping of product types (13 groups) — not a Safety Gate field |
| brand | text | Most frequent original spelling among brands with the same `brand_key` |
| brand_key | text | Case-, accent- and punctuation-insensitive matching key |
| origin_is_eu | bool | Origin is an EU member state (empty for `Unknown`) |
| origin_same_as_notifier | bool | Origin country = notifying country |
| risk_type_count, is_chemical, is_microbiological | int, bool | Derived from `risk_type` |
| alert_states_prohibited | bool | Risk text uses *prohibited / forbidden / banned* (the authority's wording) |
| based_on_ingredient_list | bool | Risk text says the finding comes from the ingredient list |
| has_measured_value | bool | Risk text reports a laboratory measurement |
| undeclared_ingredient | bool | Risk text says a substance is missing from the ingredient list |
| weekly_report, weekly_report_date | text, date | Official weekly report (XML) in which the alert appeared — **time axis used in all analyses** |
| publication_date | date | Alert `publicationDate` from the official XML; can be later than the weekly report (see `reports/date_investigation.md`) |
| xml_matched, xml_category | bool, text | Alert found in the official XML; category there |
| first_measure_date | date | Earliest parsed *Date of entry into force* of the alert's measures |
| chemical_substance_count | int | Number of distinct chemicals extracted from the risk text |
| primary_substance | text | First substance/agent named in the risk text |

## 3. Bridge and detail tables (`data/processed/`)

| File | Grain | Key columns |
|---|---|---|
| `alert_risk_types.csv` | alert × risk type | `risk_type`, `is_primary` (first listed) |
| `alert_measures.csv` | one corrective measure | `measure_kind` (compulsory/voluntary), `economic_operator`, `measure_category` (original wording), `measure_group` (10 groups), `entry_into_force_raw`, `entry_into_force_date` |
| `alert_also_found.csv` | alert × additional country | `country_raw`, `country` |
| `alert_substances.csv` | alert × substance/agent | `substance` (canonical name), `abbreviation`, `agent_type` (chemical/microorganism), `substance_group`, `cas_number` (reference data, PubChem-checked), `matched_text`, `method`, `confidence` (confirmed/uncertain), `mention_order`, `is_primary` |
| `substance_candidates_uncertain.csv` | unrecognised candidate | `candidate_text` — for manual review |
| `data_quality_issues.csv` | flagged issue | `issue_type`, `detail` |
| `xml_cosmetics_alerts.csv` | alert in official XML (category Cosmetics, 2020 and 2024–2026 reports) | XML field names (`caseNumber`, `publicationDate`, `report_reference`, …) |

## 4. Reference data (`data/reference/`)

| File | Content |
|---|---|
| `substance_dictionary.csv` | 67 substances/agents with aliases (regex), group and CAS number |
| `cas_verification.csv` | CAS check result per substance against PubChem synonyms |
| `product_mapping.csv`, `brand_mapping.csv` | Raw → standardised values with alert counts |

## 5. Database and Power BI

SQLite tables: see `docs/DATABASE.md`. Power BI tables (`Alerts`, `Substances`, `AlertSubstances`,
`CorrectiveMeasures`, `AlertRiskTypes`, `Calendar`): see `docs/POWER_BI_GUIDE.md`.
