# Executive Summary — SafetyScope

**Scope.** 1,714 EU Safety Gate alerts in the *Cosmetics* category, selected by the portal's 2025 filter
(downloaded 27 November 2026). An *alert* is a notification by a national authority about a product it found
non-compliant. Counts describe enforcement activity, **not** how often products are unsafe, market shares or a ranking
of countries: no denominator (products on the market, inspections carried out) is available.

## Key findings (verified from the data)

1. **One substance dominates.** BMHCA (2-(4-tert-butylbenzyl)propionaldehyde, also known as Lilial) is named in
   **1,488 alerts (86.8%)**. The next substances are far behind: Diphenyl(2,4,6-trimethylbenzoyl)phosphine oxide (53),
   Hydroxyisohexyl 3-cyclohexene carboxaldehyde (43), Hydroquinone (35). 57 distinct chemicals appear in total;
   24 of them in a single alert only. BMHCA has been on the EU list of prohibited cosmetic
   ingredients since 1 March 2022 (Regulation (EU) 2021/1902, see `docs/REGULATORY_CONTEXT.md`).
2. **Fragrances are the largest product group** with 764 alerts (44.6%), almost all
   of them BMHCA (99.5%). Eau de toilette and perfume alone account for 696 alerts.
3. **Substances are product-specific.** TPO and TMPTA are nail-product substances (100.0% of TPO alerts are nail
   products); hydroquinone, mercury and clobetasol propionate are concentrated in skin-lightening products
   (55 alerts): 43 of the 48 with a known origin come from outside the EU,
   and 32 were rejected at the border (Sweden notified 35 of them).
4. **Three countries submitted 87.7% of alerts**; Italy alone 1,129 (65.9%).
5. **Notifying-country profiles differ sharply.** Italy, Czechia and Hungary notify almost exclusively BMHCA cases
   identified from the ingredient list. Germany, France and Northern Ireland notify fewer but more varied cases, often
   based on laboratory measurements and voluntary company measures (queries q06, q13).
6. **Corrective measures:** a ban on marketing is reported in 75.4% of alerts, withdrawal in 15.1%,
   destruction in 11.3%, recall from consumers in 8.2%. Voluntary (company-initiated) measures
   appear in 6.5% of alerts.
7. **Alerts are published long after the measure.** Median 289 days between the first measure's entry into
   force and the weekly report (interquartile range 127–406 days).
8. **Origin:** 267 alerts (15.6%) have unknown origin. Of the known origins,
   78.5% are EU member states; most frequent: Italy (598), Germany (144), France (129), Spain (102), China (83).

## Why does Italy account for so many notifications?

Evidence from the data (verified):

| Indicator | Italy | All other notifiers |
|---|---|---|
| Share of alerts naming BMHCA as primary substance | 97.2% | 66.5% |
| Share based on the product's ingredient list | 99.5% | 75.6% |
| Share with a laboratory measurement | 0.1% | 12.1% |
| Median days from first measure to weekly report | 359 | 53 |

- 51.4% of Italy's alerts concern products of Italian origin; 99.9% carry an
  authority-ordered (compulsory) measure.
- Italy's alerts are spread over 42 weekly reports, but the 10 largest reports hold
  51.6% of them (maximum 105 in Report-2025-15).
- 92.6% of Italy's dated measures took effect in 2023–2024, although the alerts were published in 2025.

**Interpretation (hypothesis, not verified):** the pattern is consistent with a large-scale, label-based
enforcement of the BMHCA prohibition by Italian authorities — checking ingredient lists of products already on the
market — whose results were notified to Safety Gate in batches, often a year or more after the national measure.
The data cannot show *why* Italy did this, nor whether other countries found fewer cases or simply notified fewer:
notification practices, inspection priorities and market size all affect the counts, and none of them is in the data.

## Timing

Alerts are dated by the official weekly report in which they appeared. Activity in 2025 covered
52 weekly reports; the busiest month was 2025-04 (276 alerts).
**All 53 TPO alerts appeared in weekly reports dated on or after 1 September 2025** (0 before),
the date from which Regulation (EU) 2025/877 moved TPO to the list of prohibited substances. This timing is descriptive:
the data show the coincidence, not the authorities' reasons.

## What this means for a business audience (interpretation)

- **Fragrance and personal-care importers/distributors:** BMHCA-containing stock is the dominant enforcement issue in
  this period; ingredient-list screening alone triggers alerts, so label review is a low-cost control.
- **Nail-product suppliers:** TPO, TMPTA and HEMA recur; TPO's change from restricted to prohibited status from
  1 September 2025 makes it a substance to monitor.
- **Skin-lightening products from outside the EU** are named with mercury, hydroquinone and clobetasol propionate,
  and are mostly stopped at the external border (border rejection in 32 of 55 alerts) —
  relevant for import compliance checks.

## Limitations

- One export, one portal filter, whose exact definition is not documented (see `reports/date_investigation.md`).
- Counts are notifications, not prevalence; country comparisons reflect enforcement and reporting activity.
- Substance extraction is rule-based and evaluated against AI-produced labels pending human review
  (`reports/substance_extraction_evaluation.md`).
- Product groups are a project-defined classification.

Figures: `reports/figures/`. All numbers: `reports/key_metrics.json`, generated by `src/findings.py`.
