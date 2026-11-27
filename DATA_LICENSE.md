# Data Licensing and Attribution

The **software** in this repository is licensed under the MIT License (`LICENSE`). The **data** is not covered by
that licence; it remains subject to the terms of its original publishers, summarised below.

## Safety Gate alert data (European Commission)

Files: `data/search_list_20261127_notification_list.xlsx`, `analysis/cosmetics_working_data.xlsx` (data sheet),
`data/external/`, `data/processed/`, `powerbi/data/`, `powerbi/SafetyScope_PowerBI_upload.xlsx`, and all tables,
figures and screenshots derived from them.

The Safety Gate disclaimer (PDF linked from the portal footer, read 27 Nov 2026) states that reuse of information
published on Safety Gate is authorised provided the original meaning of the alerts is not distorted and the source
is acknowledged as follows:

> Alerts from the Rapid Alert System for dangerous non-food products, published free of charge on the Safety Gate
> website (https://ec.europa.eu/safety-gate-alerts) © European Union, 2005 – 2026

The reuse policy is set out in Commission Decision 2011/833/EU; the portal's legal-notice link points to the
Commission's general legal notice (CC BY 4.0 for Commission-owned content unless stated otherwise).

Important conditions from the disclaimer:
- Information in alerts is provided by national contact points; the Commission is not liable for its accuracy.
- Brands, designs and logos in alerts may have been used by economic operators without the owner's permission.
  Brand names in this project identify what was written in an alert, not wrongdoing by the brand owner.
- Product **photos are not included** in this repository (only their URLs appear in the XML-derived CSV).

**Modifications:** the data has been cleaned and restructured (see `reports/cleaning_report.md`); original values
are kept alongside cleaned values. Derived fields (product groups, extracted substances) are the project's own work.

## Other sources

| Source | Use | Terms |
|---|---|---|
| EUR-Lex (Regulations (EU) 2021/1902 and 2025/877) | Facts and dates cited in `docs/REGULATORY_CONTEXT.md`; no text copied beyond short citations | EUR-Lex legal notice (terms not re-checked in this project) |
| PubChem (NIH/NLM) | Only used to check CAS numbers; no PubChem content redistributed beyond the yes/no result | PubChem data policy (terms not re-checked in this project) |
| Microsoft JSON schemas | Validation of Power BI files (`powerbi/tools/schemas/`) | MIT License (copy included) |
| Hugging Face model `OpenMed/OpenMed-NER-ChemicalDetect-PubMed-109M` | Comparison only; **weights not redistributed** | Apache-2.0 (model card) |

## Manually created or AI-assisted content

`data/evaluation/reference_labels_ai.csv` was produced by an AI assistant (Claude) and is not human ground truth.
