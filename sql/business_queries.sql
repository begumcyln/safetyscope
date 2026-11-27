-- SafetyScope business queries (SQLite)
-- Run all of them with:  python src/run_sql.py   -> reports/sql_results.md
--
-- Conventions
-- * The unit of every count is a Safety Gate ALERT (notification), not a product
--   sold, a company or an inspection. Counts are not defect rates.
-- * Whenever a bridge table (alert_substance, alert_measure, alert_risk_type)
--   is joined, alerts are counted with COUNT(DISTINCT alert_number).
-- * Each query starts with "-- name:" and "-- question:" lines used by the runner.

-- name: q01_alerts_by_product_group
-- question: Which product categories account for the largest number of alerts?
SELECT pt.product_group,
       COUNT(*)                                                   AS alerts,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM alert), 1)  AS share_pct,
       COUNT(DISTINCT pt.product_type)                            AS product_types
FROM alert a
JOIN product_type pt USING (product_type_id)
GROUP BY pt.product_group
ORDER BY alerts DESC;

-- name: q02_top_product_types
-- question: Which individual product types are notified most often?
SELECT pt.product_type, pt.product_group, COUNT(*) AS alerts,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM alert), 1) AS share_pct
FROM alert a JOIN product_type pt USING (product_type_id)
GROUP BY pt.product_type, pt.product_group
ORDER BY alerts DESC
LIMIT 15;

-- name: q03_top_substances
-- question: Which chemical substances occur most frequently in alerts?
SELECT s.substance, s.abbreviation, s.substance_group,
       COUNT(DISTINCT x.alert_number) AS alerts,
       ROUND(100.0 * COUNT(DISTINCT x.alert_number) / (SELECT COUNT(*) FROM alert), 1) AS share_of_all_alerts_pct
FROM alert_substance x
JOIN substance s USING (substance_id)
WHERE s.agent_type = 'chemical' AND x.confidence = 'confirmed'
GROUP BY s.substance_id
ORDER BY alerts DESC
LIMIT 15;

-- name: q04_substance_concentration
-- question: How concentrated are chemical alerts in a few substances?
WITH per_sub AS (
    SELECT s.substance, COUNT(DISTINCT x.alert_number) AS alerts
    FROM alert_substance x JOIN substance s USING (substance_id)
    WHERE s.agent_type = 'chemical'
    GROUP BY s.substance
), ranked AS (
    SELECT substance, alerts, ROW_NUMBER() OVER (ORDER BY alerts DESC) AS rnk FROM per_sub
)
SELECT (SELECT COUNT(*) FROM per_sub)                                      AS distinct_chemicals,
       (SELECT COUNT(DISTINCT alert_number) FROM alert_substance x
          JOIN substance s USING (substance_id) WHERE s.agent_type = 'chemical') AS alerts_with_a_chemical,
       (SELECT substance FROM ranked WHERE rnk = 1)                        AS top_substance,
       ROUND(100.0 * (SELECT alerts FROM ranked WHERE rnk = 1) /
             (SELECT COUNT(DISTINCT alert_number) FROM alert_substance x
                JOIN substance s USING (substance_id) WHERE s.agent_type = 'chemical'), 1) AS top_substance_share_pct,
       (SELECT COUNT(*) FROM per_sub WHERE alerts = 1)                     AS chemicals_named_in_only_one_alert;

-- name: q05_substance_by_product_group
-- question: Which substances are associated with particular product groups? (top 3 substances per group)
WITH pairs AS (
    SELECT pt.product_group, s.substance, COUNT(DISTINCT a.alert_number) AS alerts
    FROM alert a
    JOIN product_type pt USING (product_type_id)
    JOIN alert_substance x USING (alert_number)
    JOIN substance s USING (substance_id)
    GROUP BY pt.product_group, s.substance
), totals AS (
    SELECT pt.product_group, COUNT(*) AS group_alerts
    FROM alert a JOIN product_type pt USING (product_type_id) GROUP BY pt.product_group
), ranked AS (
    SELECT p.*, t.group_alerts,
           ROUND(100.0 * p.alerts / t.group_alerts, 1) AS pct_of_group_alerts,
           ROW_NUMBER() OVER (PARTITION BY p.product_group ORDER BY p.alerts DESC, p.substance) AS rnk
    FROM pairs p JOIN totals t USING (product_group)
)
SELECT product_group, group_alerts, rnk AS rank_in_group, substance, alerts, pct_of_group_alerts
FROM ranked
WHERE rnk <= 3
ORDER BY group_alerts DESC, rnk;

-- name: q06_notifying_country_profiles
-- question: How do notifying-country profiles differ?
SELECT a.notifying_country,
       COUNT(*)                                                        AS alerts,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM alert), 1)       AS share_pct,
       ROUND(100.0 * AVG(a.primary_substance = 'Butylphenyl methylpropional'), 1) AS pct_bmhca,
       ROUND(100.0 * AVG(a.based_on_ingredient_list), 1)               AS pct_based_on_ingredient_list,
       ROUND(100.0 * AVG(a.has_measured_value), 1)                     AS pct_with_lab_measurement,
       ROUND(100.0 * AVG(a.origin_country = 'Unknown'), 1)             AS pct_origin_unknown,
       ROUND(100.0 * AVG(a.origin_same_as_notifier), 1)                AS pct_domestic_origin,
       COUNT(DISTINCT a.primary_substance)                             AS distinct_primary_substances,
       COUNT(DISTINCT a.product_type_id)                               AS distinct_product_types
FROM alert a
GROUP BY a.notifying_country
ORDER BY alerts DESC;

-- name: q07_italy_composition
-- question: What are Italy's notifications made of (product group x substance)?
SELECT pt.product_group,
       COALESCE(a.primary_substance, '(none)') AS primary_substance,
       COUNT(*) AS alerts,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM alert WHERE notifying_country = 'Italy'), 1) AS pct_of_italy
FROM alert a JOIN product_type pt USING (product_type_id)
WHERE a.notifying_country = 'Italy'
GROUP BY pt.product_group, a.primary_substance
ORDER BY alerts DESC
LIMIT 10;

-- name: q08_italy_vs_rest_bmhca_fragrance
-- question: Is Italy's share driven by one substance/product combination?
SELECT CASE WHEN notifying_country = 'Italy' THEN 'Italy' ELSE 'All other notifiers' END AS notifier,
       COUNT(*) AS alerts,
       SUM(primary_substance = 'Butylphenyl methylpropional') AS bmhca_alerts,
       SUM(pt.product_group = 'Fragrance') AS fragrance_alerts,
       SUM(primary_substance = 'Butylphenyl methylpropional' AND pt.product_group = 'Fragrance') AS bmhca_fragrance_alerts,
       ROUND(100.0 * AVG(primary_substance = 'Butylphenyl methylpropional'), 1) AS pct_bmhca,
       ROUND(100.0 * AVG(a.origin_country = 'Italy'), 1) AS pct_origin_italy
FROM alert a JOIN product_type pt USING (product_type_id)
GROUP BY notifier;

-- name: q09_italy_weekly_concentration
-- question: Are Italy's notifications concentrated in a few weekly reports?
WITH weekly AS (
    SELECT weekly_report, COUNT(*) AS italy_alerts
    FROM alert WHERE notifying_country = 'Italy'
    GROUP BY weekly_report
), ranked AS (
    SELECT weekly_report, italy_alerts,
           ROW_NUMBER() OVER (ORDER BY italy_alerts DESC) AS rnk,
           SUM(italy_alerts) OVER () AS italy_total
    FROM weekly
)
SELECT (SELECT COUNT(*) FROM weekly)                                   AS weekly_reports_with_italian_alerts,
       (SELECT MAX(italy_alerts) FROM weekly)                          AS max_italian_alerts_in_one_report,
       (SELECT weekly_report FROM ranked WHERE rnk = 1)                AS busiest_report,
       ROUND(100.0 * (SELECT SUM(italy_alerts) FROM ranked WHERE rnk <= 5) / MAX(italy_total), 1) AS pct_in_top5_reports,
       ROUND(100.0 * (SELECT SUM(italy_alerts) FROM ranked WHERE rnk <= 10) / MAX(italy_total), 1) AS pct_in_top10_reports
FROM ranked;

-- name: q10_origin_profile_by_substance
-- question: Where do products with the main substances come from? (known origins only)
WITH base AS (
    SELECT s.substance, a.origin_country, COUNT(DISTINCT a.alert_number) AS alerts
    FROM alert a
    JOIN alert_substance x USING (alert_number)
    JOIN substance s USING (substance_id)
    WHERE a.origin_country <> 'Unknown'
      AND s.substance IN (SELECT s2.substance FROM alert_substance x2 JOIN substance s2 USING (substance_id)
                          GROUP BY s2.substance ORDER BY COUNT(*) DESC LIMIT 6)
    GROUP BY s.substance, a.origin_country
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY substance ORDER BY alerts DESC, origin_country) AS rnk,
           SUM(alerts) OVER (PARTITION BY substance) AS known_origin_alerts
    FROM base
)
SELECT substance, known_origin_alerts, rnk AS rank, origin_country, alerts,
       ROUND(100.0 * alerts / known_origin_alerts, 1) AS pct_of_known_origin
FROM ranked WHERE rnk <= 3
ORDER BY known_origin_alerts DESC, rnk;

-- name: q11_origin_eu_vs_non_eu
-- question: What share of alerts concern products of EU vs non-EU origin?
SELECT CASE c.is_eu_member WHEN 1 THEN 'EU member state' WHEN 0 THEN 'Non-EU' ELSE 'Unknown' END AS origin,
       COUNT(*) AS alerts,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM alert), 1) AS share_pct
FROM alert a JOIN country c ON c.country_name = a.origin_country
GROUP BY origin ORDER BY alerts DESC;

-- name: q12_corrective_measures
-- question: Which corrective measures are most frequently reported?
SELECT m.measure_group,
       COUNT(DISTINCT m.alert_number)                                     AS alerts,
       ROUND(100.0 * COUNT(DISTINCT m.alert_number) / (SELECT COUNT(*) FROM alert), 1) AS pct_of_alerts,
       SUM(m.measure_kind = 'compulsory')                                 AS compulsory_measures,
       SUM(m.measure_kind = 'voluntary')                                  AS voluntary_measures
FROM alert_measure m
GROUP BY m.measure_group
ORDER BY alerts DESC;

-- name: q13_measure_mix_by_country
-- question: Do countries rely on compulsory (authority-ordered) or voluntary (company) measures?
SELECT a.notifying_country,
       COUNT(DISTINCT a.alert_number) AS alerts,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN m.measure_kind = 'compulsory' THEN a.alert_number END)
             / COUNT(DISTINCT a.alert_number), 1) AS pct_with_compulsory,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN m.measure_kind = 'voluntary' THEN a.alert_number END)
             / COUNT(DISTINCT a.alert_number), 1) AS pct_with_voluntary,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN m.measure_group = 'Recall from end users' THEN a.alert_number END)
             / COUNT(DISTINCT a.alert_number), 1) AS pct_with_recall
FROM alert a JOIN alert_measure m USING (alert_number)
GROUP BY a.notifying_country
HAVING COUNT(DISTINCT a.alert_number) >= 20
ORDER BY alerts DESC;

-- name: q14_measures_by_substance
-- question: Do corrective measures differ between the main substances?
SELECT s.substance,
       COUNT(DISTINCT x.alert_number) AS alerts,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN m.measure_group = 'Ban on marketing' THEN x.alert_number END) / COUNT(DISTINCT x.alert_number), 1) AS pct_ban,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN m.measure_group = 'Withdrawal from market' THEN x.alert_number END) / COUNT(DISTINCT x.alert_number), 1) AS pct_withdrawal,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN m.measure_group = 'Recall from end users' THEN x.alert_number END) / COUNT(DISTINCT x.alert_number), 1) AS pct_recall,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN m.measure_group = 'Destruction' THEN x.alert_number END) / COUNT(DISTINCT x.alert_number), 1) AS pct_destruction
FROM alert_substance x
JOIN substance s USING (substance_id)
JOIN alert_measure m USING (alert_number)
GROUP BY s.substance
HAVING COUNT(DISTINCT x.alert_number) >= 15
ORDER BY alerts DESC;

-- name: q15_monthly_trend
-- question: How are alerts distributed over the reporting period (by weekly report month)?
SELECT substr(weekly_report_date, 1, 7)                         AS report_month,
       COUNT(*)                                                 AS alerts,
       SUM(primary_substance = 'Butylphenyl methylpropional')   AS bmhca_alerts,
       SUM(notifying_country = 'Italy')                         AS italy_alerts
FROM alert
GROUP BY report_month
ORDER BY report_month;

-- name: q16_time_to_publication
-- question: How long after the first corrective measure does an alert appear in a weekly report? (days; SQLite has no MEDIAN, so quartiles are taken by row position)
WITH lags AS (
    SELECT julianday(weekly_report_date) - julianday(first_measure_date) AS lag_days
    FROM alert
    WHERE first_measure_date IS NOT NULL AND weekly_report_date IS NOT NULL
), ranked AS (
    SELECT lag_days, ROW_NUMBER() OVER (ORDER BY lag_days) AS rn, COUNT(*) OVER () AS n FROM lags
)
SELECT MAX(n)                                                      AS alerts_with_measure_date,
       MAX(CASE WHEN rn = CAST(n * 0.25 AS INT) THEN lag_days END) AS p25_days,
       MAX(CASE WHEN rn = CAST(n * 0.50 AS INT) THEN lag_days END) AS median_days,
       MAX(CASE WHEN rn = CAST(n * 0.75 AS INT) THEN lag_days END) AS p75_days,
       ROUND(AVG(lag_days))                                        AS mean_days,
       SUM(lag_days < 0)                                           AS measure_after_report
FROM ranked;

-- name: q17_multi_substance_alerts
-- question: How many alerts name more than one substance, and which pairs co-occur?
SELECT s1.substance AS substance_a, s2.substance AS substance_b, COUNT(*) AS alerts
FROM alert_substance x1
JOIN alert_substance x2 ON x1.alert_number = x2.alert_number AND x1.substance_id < x2.substance_id
JOIN substance s1 ON s1.substance_id = x1.substance_id
JOIN substance s2 ON s2.substance_id = x2.substance_id
GROUP BY substance_a, substance_b
ORDER BY alerts DESC
LIMIT 10;

-- name: q18_double_counting_demo
-- question: Why COUNT(DISTINCT) matters: naive vs correct alert counts after joining measures
SELECT 'Rows after joining alert_measure (naive COUNT(*))' AS method, COUNT(*) AS value
FROM alert a JOIN alert_measure m USING (alert_number)
UNION ALL
SELECT 'Distinct alerts (COUNT(DISTINCT alert_number))', COUNT(DISTINCT a.alert_number)
FROM alert a JOIN alert_measure m USING (alert_number);

-- name: q19_top_brands
-- question: Which brand names appear in most alerts? (brand names may be misused by third parties - see disclaimer)
SELECT brand, COUNT(*) AS alerts,
       COUNT(DISTINCT notifying_country) AS notifying_countries,
       GROUP_CONCAT(DISTINCT primary_substance) AS substances
FROM alert
WHERE brand IS NOT NULL
GROUP BY brand
ORDER BY alerts DESC
LIMIT 10;

-- name: q20_data_quality_overview
-- question: What data quality caveats apply to these results?
SELECT 'Alerts' AS metric, COUNT(*) AS value FROM alert
UNION ALL SELECT 'Origin country unknown', SUM(origin_country = 'Unknown') FROM alert
UNION ALL SELECT 'Brand missing', SUM(brand IS NULL) FROM alert
UNION ALL SELECT 'No substance/agent extracted', SUM(primary_substance IS NULL) FROM alert
UNION ALL SELECT 'Measures with unknown entry-into-force date', SUM(entry_into_force_date IS NULL) FROM alert_measure
UNION ALL SELECT 'Uncertain substance candidates', COUNT(*) FROM substance_candidate
UNION ALL SELECT 'Alerts not matched to an official weekly report', SUM(weekly_report IS NULL) FROM alert;
