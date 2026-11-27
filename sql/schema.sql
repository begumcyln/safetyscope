-- SafetyScope SQLite schema
-- Star-like model: one fact table (alert) + dimensions + bridge tables for
-- multivalued attributes. Rebuilt from scratch by src/pipeline.py.
--
--   country ──< alert >── product_type
--                 │
--     ┌───────────┼──────────────┬─────────────────┐
--  alert_risk_type  alert_substance  alert_measure  alert_also_found
--        │               │
--   risk_type        substance
--
-- Counting rule: COUNT(DISTINCT a.alert_number) whenever a bridge table is
-- joined, because one alert can have several risks/substances/measures.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS alert_also_found;
DROP TABLE IF EXISTS alert_measure;
DROP TABLE IF EXISTS alert_substance;
DROP TABLE IF EXISTS alert_risk_type;
DROP TABLE IF EXISTS substance_candidate;
DROP TABLE IF EXISTS alert;
DROP TABLE IF EXISTS substance;
DROP TABLE IF EXISTS risk_type;
DROP TABLE IF EXISTS product_type;
DROP TABLE IF EXISTS country;
DROP TABLE IF EXISTS raw_export;

CREATE TABLE country (
    country_name   TEXT PRIMARY KEY,      -- display name, e.g. 'China'
    safety_gate_label TEXT NOT NULL,      -- label used by Safety Gate, e.g. 'People''s Republic of China'
    iso2           TEXT,                  -- ISO 3166-1 alpha-2 (XI = Northern Ireland)
    is_eu_member   INTEGER                -- 1/0, NULL for 'Unknown'
);

CREATE TABLE product_type (
    product_type_id INTEGER PRIMARY KEY,
    product_type    TEXT NOT NULL UNIQUE,  -- standardised Safety Gate 'Product' value
    product_group   TEXT NOT NULL          -- project-defined analytical grouping
);

CREATE TABLE risk_type (
    risk_type_id INTEGER PRIMARY KEY,
    risk_type    TEXT NOT NULL UNIQUE
);

CREATE TABLE substance (
    substance_id    INTEGER PRIMARY KEY,
    substance       TEXT NOT NULL UNIQUE,
    abbreviation    TEXT,
    agent_type      TEXT NOT NULL CHECK (agent_type IN ('chemical', 'microorganism')),
    substance_group TEXT,
    cas_number      TEXT                   -- project reference data, not from Safety Gate
);

CREATE TABLE alert (
    alert_number          TEXT PRIMARY KEY,   -- e.g. SR/01834/25
    case_id               TEXT UNIQUE,        -- numeric id in the case URL
    case_url              TEXT NOT NULL,
    alert_prefix          TEXT,
    alert_number_year     INTEGER,            -- 20YY suffix of the alert number
    publication_date      TEXT,               -- from official XML (ISO date), NULL if not matched
    weekly_report         TEXT,               -- e.g. Report-2025-14
    weekly_report_date    TEXT,               -- Friday the weekly report was published (ISO date)
    first_measure_date    TEXT,               -- earliest 'Date of entry into force'
    alert_level           TEXT,
    user_type             TEXT,
    notifying_country     TEXT REFERENCES country(country_name),
    origin_country        TEXT REFERENCES country(country_name),
    origin_same_as_notifier INTEGER,
    product_type_id       INTEGER REFERENCES product_type(product_type_id),
    product_name          TEXT,
    brand                 TEXT,
    brand_raw             TEXT,
    counterfeit           TEXT,
    risk_type_combined    TEXT,               -- original multivalued label
    risk_description      TEXT,
    legal_provision       TEXT,
    alert_states_prohibited INTEGER,          -- the alert text says prohibited/forbidden/banned
    undeclared_ingredient INTEGER,
    has_measured_value    INTEGER,
    based_on_ingredient_list INTEGER,
    chemical_substance_count INTEGER,
    primary_substance     TEXT,
    barcode               TEXT,
    batch_number          TEXT,
    source_file           TEXT,
    source_row            INTEGER
);

CREATE TABLE alert_risk_type (
    alert_number TEXT NOT NULL REFERENCES alert(alert_number),
    risk_type_id INTEGER NOT NULL REFERENCES risk_type(risk_type_id),
    is_primary   INTEGER NOT NULL,
    PRIMARY KEY (alert_number, risk_type_id)
);

CREATE TABLE alert_substance (
    alert_number  TEXT NOT NULL REFERENCES alert(alert_number),
    substance_id  INTEGER NOT NULL REFERENCES substance(substance_id),
    mention_order INTEGER NOT NULL,
    is_primary    INTEGER NOT NULL,
    matched_text  TEXT,
    method        TEXT NOT NULL,
    confidence    TEXT NOT NULL CHECK (confidence IN ('confirmed', 'uncertain')),
    PRIMARY KEY (alert_number, substance_id)
);

CREATE TABLE alert_measure (
    measure_id         INTEGER PRIMARY KEY,
    alert_number       TEXT NOT NULL REFERENCES alert(alert_number),
    measure_kind       TEXT NOT NULL CHECK (measure_kind IN ('compulsory', 'voluntary')),
    measure_seq        INTEGER NOT NULL,
    economic_operator  TEXT,
    measure_category   TEXT,                -- original Safety Gate wording
    measure_group      TEXT,                -- grouped category
    entry_into_force_date TEXT,             -- ISO date or NULL ('Unknown')
    entry_into_force_raw  TEXT
);

CREATE TABLE alert_also_found (
    alert_number TEXT NOT NULL REFERENCES alert(alert_number),
    country      TEXT NOT NULL,
    PRIMARY KEY (alert_number, country)
);

CREATE TABLE substance_candidate (
    alert_number   TEXT NOT NULL REFERENCES alert(alert_number),
    candidate_text TEXT NOT NULL,
    method         TEXT NOT NULL,
    confidence     TEXT NOT NULL
);

-- Untouched copy of the export rows (all text), for traceability.
CREATE TABLE raw_export (
    source_file TEXT, source_row INTEGER,
    type_of_alert TEXT, type TEXT, alert_number TEXT, alert_submitted_by TEXT,
    country_of_origin TEXT, counterfeit TEXT, risk_type TEXT, risk_legal_provision TEXT,
    product TEXT, name TEXT, description TEXT, brand TEXT, category TEXT, model TEXT,
    oecd_portal_category TEXT, risk TEXT, compulsory_measures TEXT, voluntary_measures TEXT,
    also_found_in TEXT, company_recall_page TEXT, url_of_case TEXT, barcode TEXT,
    batch_number TEXT, packaging_description TEXT, online_trader TEXT
);

CREATE INDEX idx_alert_notifier ON alert(notifying_country);
CREATE INDEX idx_alert_origin ON alert(origin_country);
CREATE INDEX idx_alert_product ON alert(product_type_id);
CREATE INDEX idx_alert_substance_sub ON alert_substance(substance_id);
CREATE INDEX idx_alert_measure_alert ON alert_measure(alert_number);
