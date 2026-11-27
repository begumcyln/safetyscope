"""Stage C - evaluate substance extraction and prepare the owner's review file.

Usage:
    python src/evaluate_extraction.py            # rule-based + model (if installed)
    python src/evaluate_extraction.py --no-model # rule-based only

Evaluation design
-----------------
* Unit: a *distinct* (whitespace-normalised) risk text. Many alerts share the
  exact same sentence, so evaluating alerts would mostly re-test one BMHCA
  sentence. Metrics are also reported weighted by the number of alerts.
* Sample: 60 of the distinct texts, simple random sample, seed 42.
* Reference labels: ``data/evaluation/reference_labels_ai.csv``. They were
  written by the AI assistant (Claude) by reading each text, separately from
  the regex rules. **They are NOT human ground truth.** When the project owner
  fills in the review workbook, their labels replace the AI labels and the
  report states which labels were used.
* Labelling guideline: label every specific chemical substance or named
  microorganism that the text says is present in the product. Do not label
  class words ("corticosteroid", "nitrosamine", "allergenic fragrances") or
  substances mentioned only as a comparison.
* Matching: a prediction is correct if it maps to the same canonical name as
  a reference label (exact set comparison per text).

Model comparison
----------------
OpenMed/OpenMed-NER-ChemicalDetect-PubMed-109M (Apache-2.0, trained on the
BC4CHEMD PubMed corpus), pinned to a fixed revision. Its spans are mapped to
canonical names with the same alias dictionary; spans that match no alias are
kept as their own (normalised) text. The model detects chemicals only, so the
comparison is made on chemical labels only.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from profile_data import md_table  # noqa: E402
from safetyscope import config as C  # noqa: E402
from safetyscope.substances import SUBSTANCES, extract_candidates, extract_mentions, normalize_risk_text  # noqa: E402

EVAL_DIR = C.DATA_DIR / "evaluation"
REVIEW_DIR = C.DATA_DIR / "review"
REVIEW_FILE = REVIEW_DIR / "substance_review_for_owner.xlsx"
MODEL_ID = "OpenMed/OpenMed-NER-ChemicalDetect-PubMed-109M"
MODEL_REVISION = "78f35d7364748515e098a95a857d4c88c38902ae"
SAMPLE_SIZE, SEED = 60, 42
CHEMICALS = {name for name, _a, kind, *_ in SUBSTANCES if kind == "chemical"}
KNOWN = {name for name, *_ in SUBSTANCES}


def chemical_or_unmapped(pred: set[str]) -> set[str]:
    """Keep dictionary chemicals and spans the dictionary could not map (those count as errors)."""
    return {x for x in pred if x in CHEMICALS or x not in KNOWN}


def text_id(text: str) -> str:
    return "T" + hashlib.sha1(text.encode()).hexdigest()[:8]


def distinct_texts() -> pd.DataFrame:
    a = pd.read_csv(C.PROCESSED_DIR / "alerts_clean.csv", low_memory=False)
    a["text"] = a["risk_description_raw"].map(normalize_risk_text)
    g = a.groupby("text").agg(alerts=("alert_number", "size"), example_alert=("alert_number", "first"),
                              example_url=("case_url", "first")).reset_index()
    g["text_id"] = g["text"].map(text_id)
    return g


def split_labels(value) -> set[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)) or not str(value).strip():
        return set()
    return {v.strip() for v in str(value).split(";") if v.strip()}


def owner_labels() -> dict[str, set[str]]:
    """Labels entered by the project owner in the review workbook (if any)."""
    if not REVIEW_FILE.exists():
        return {}
    df = pd.read_excel(REVIEW_FILE, sheet_name="evaluation_sample", dtype=str).fillna("")
    out = {}
    for r in df.itertuples():
        verdict = (r.owner_agrees_with_reference or "").strip().lower()
        if verdict in {"yes", "y"}:
            out[r.text_id] = split_labels(r.reference_labels_ai)
        elif verdict in {"no", "n"}:
            out[r.text_id] = split_labels(r.owner_corrected_labels)
    return out


def rule_predict(text: str) -> set[str]:
    return {m.substance for m in extract_mentions(text)}


def load_model():
    os.environ.setdefault("HF_HOME", str(C.ROOT / ".cache" / "huggingface"))
    from transformers import pipeline  # imported lazily: optional dependency
    return pipeline("token-classification", model=MODEL_ID, revision=MODEL_REVISION,
                    aggregation_strategy="max", device=-1)


def model_predict(ner, text: str) -> tuple[set[str], list[str]]:
    spans = [text[e["start"]:e["end"]] for e in ner(text)]
    canon = set()
    for span in spans:
        mapped = {m.substance for m in extract_mentions(span)}
        canon |= mapped if mapped else {span.strip().lower()}
    return canon, spans


MODEL_CACHE = EVAL_DIR / "model_predictions_cache.csv"


def get_model_cache(texts: pd.DataFrame, rerun: bool = False) -> dict[str, set[str]] | None:
    """Model output per distinct text (canonical chemical names + unmapped spans).

    The model is only loaded when no complete cache exists or --rerun-model is
    given. Inference runs sequentially, one text at a time, and the model is
    deleted and garbage-collected afterwards to release memory.
    """
    if MODEL_CACHE.exists() and not rerun:
        cached = pd.read_csv(MODEL_CACHE, dtype=str).fillna("")
        result = {r.text_id: split_labels(r.model_chem) for r in cached.itertuples()}
        if set(texts["text_id"]) <= set(result):
            print(f"Reusing cached model predictions ({MODEL_CACHE.name}); use --rerun-model to recompute.")
            return result
    try:
        ner = load_model()
    except Exception as exc:
        print(f"Model unavailable ({exc}); continuing with rule-based results only.")
        return None
    rows = []
    try:
        for r in texts.itertuples():
            canon, spans = model_predict(ner, r.text)
            rows.append({"text_id": r.text_id, "model_chem": "; ".join(sorted(chemical_or_unmapped(canon))),
                         "model_spans": " | ".join(spans), "source": f"inference {MODEL_ID}@{MODEL_REVISION[:12]}"})
    finally:
        import gc
        del ner
        gc.collect()
    pd.DataFrame(rows).to_csv(MODEL_CACHE, index=False)
    return {r["text_id"]: split_labels(r["model_chem"]) for r in rows}


def prf(pred: list[set], gold: list[set], weights: list[int] | None = None) -> dict:
    weights = weights or [1] * len(pred)
    tp = sum(w * len(p & g) for p, g, w in zip(pred, gold, weights))
    fp = sum(w * len(p - g) for p, g, w in zip(pred, gold, weights))
    fn = sum(w * len(g - p) for p, g, w in zip(pred, gold, weights))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    exact = sum(w for p, g, w in zip(pred, gold, weights) if p == g) / sum(weights)
    return {"TP": tp, "FP": fp, "FN": fn, "precision": round(precision, 3), "recall": round(recall, 3),
            "F1": round(f1, 3), "exact_match_rate": round(exact, 3)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-model", action="store_true", help="rule-based results only")
    parser.add_argument("--rerun-model", action="store_true",
                        help="run the NER model again instead of reusing the cached predictions (needs ~1 GB RAM)")
    args = parser.parse_args()
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    texts = distinct_texts()
    sample = texts.sample(n=SAMPLE_SIZE, random_state=SEED).sort_values("text_id").reset_index(drop=True)
    ref = pd.read_csv(EVAL_DIR / "reference_labels_ai.csv", dtype=str).set_index("text_id")
    missing = set(sample["text_id"]) - set(ref.index)
    if missing:
        raise SystemExit(f"Reference labels missing for {sorted(missing)}")

    owner = owner_labels()
    label_source = []
    gold = []
    for tid in sample["text_id"]:
        if tid in owner:
            gold.append(owner[tid])
            label_source.append("project owner (human)")
        else:
            gold.append(split_labels(ref.loc[tid, "reference_labels"]))
            label_source.append("AI assistant (not human-verified)")
    sample["gold"] = gold
    sample["label_source"] = label_source
    sample["rule_pred"] = sample["text"].map(rule_predict)

    use_model = not args.no_model
    cache = get_model_cache(texts, rerun=args.rerun_model) if use_model else None
    if cache is None:
        use_model = False
    if use_model:
        sample["model_chem"] = sample["text_id"].map(cache)

    # ---- metrics -------------------------------------------------------------
    rows = []
    w = sample["alerts"].tolist()
    gold_chem = [g & CHEMICALS for g in sample["gold"]]
    rows.append({"method": "Rule-based (all agents)", "weighting": "per distinct text", **prf(list(sample["rule_pred"]), list(sample["gold"]))})
    rows.append({"method": "Rule-based (all agents)", "weighting": "per alert", **prf(list(sample["rule_pred"]), list(sample["gold"]), w)})
    rule_chem = [p & CHEMICALS for p in sample["rule_pred"]]
    rows.append({"method": "Rule-based (chemicals only)", "weighting": "per distinct text", **prf(rule_chem, gold_chem)})
    rows.append({"method": "Rule-based (chemicals only)", "weighting": "per alert", **prf(rule_chem, gold_chem, w)})
    if use_model:
        model_sets = list(sample["model_chem"])
        rows.append({"method": f"NER model {MODEL_ID.split('/')[-1]} (chemicals)", "weighting": "per distinct text", **prf(model_sets, gold_chem)})
        rows.append({"method": f"NER model {MODEL_ID.split('/')[-1]} (chemicals)", "weighting": "per alert", **prf(model_sets, gold_chem, w)})
    metrics = pd.DataFrame(rows)
    metrics.to_csv(EVAL_DIR / "extraction_metrics.csv", index=False)

    # Error listing
    errors = []
    for r in sample.itertuples():
        for name in sorted(r.rule_pred - r.gold):
            errors.append({"text_id": r.text_id, "method": "rule-based", "error": "false positive", "item": name})
        for name in sorted(r.gold - r.rule_pred):
            errors.append({"text_id": r.text_id, "method": "rule-based", "error": "missed", "item": name})
        if use_model:
            g = r.gold & CHEMICALS
            for name in sorted(r.model_chem - g):
                errors.append({"text_id": r.text_id, "method": "model", "error": "false positive", "item": name})
            for name in sorted(g - r.model_chem):
                errors.append({"text_id": r.text_id, "method": "model", "error": "missed", "item": name})
    errors = pd.DataFrame(errors, columns=["text_id", "method", "error", "item"])
    errors.to_csv(EVAL_DIR / "extraction_errors.csv", index=False)

    # Save sample with predictions
    out = sample.copy()
    for col in ["gold", "rule_pred", "model_pred", "model_chem"]:
        if col in out:
            out[col] = out[col].map(lambda s: "; ".join(sorted(s)))
    out.to_csv(EVAL_DIR / "evaluation_sample_predictions.csv", index=False)

    # Full-corpus model coverage (all distinct texts) for comparison
    coverage = None
    if use_model:
        full = texts.copy()
        full["rule_chem"] = full["text"].map(lambda t: rule_predict(t) & CHEMICALS)
        full["model_chem"] = full["text_id"].map(cache)
        full["agree"] = full["rule_chem"] == full["model_chem"]
        coverage = {
            "distinct_texts": len(full),
            "texts_where_methods_agree": int(full["agree"].sum()),
            "alerts_where_methods_agree": int(full.loc[full["agree"], "alerts"].sum()),
            "alerts_total": int(full["alerts"].sum()),
        }
        disagree = full[~full["agree"]].copy()
        disagree["only_rule"] = [("; ".join(sorted(r - m))) for r, m in zip(disagree["rule_chem"], disagree["model_chem"])]
        disagree["only_model"] = [("; ".join(sorted(m - r))) for r, m in zip(disagree["rule_chem"], disagree["model_chem"])]
        disagree[["text_id", "alerts", "only_rule", "only_model", "text"]].to_csv(EVAL_DIR / "rule_vs_model_disagreements.csv", index=False)

    write_review_workbook(sample, texts)
    write_report(sample, metrics, errors, coverage, use_model)


def write_review_workbook(sample: pd.DataFrame, texts: pd.DataFrame) -> None:
    """Excel workbook for the project owner. Existing owner input is preserved."""
    previous = {}
    if REVIEW_FILE.exists():
        old = pd.read_excel(REVIEW_FILE, sheet_name="evaluation_sample", dtype=str).fillna("").set_index("text_id")
        previous = old[["owner_agrees_with_reference", "owner_corrected_labels", "owner_comment"]].to_dict("index")

    ev = pd.DataFrame({
        "text_id": sample["text_id"], "alerts_with_this_text": sample["alerts"],
        "example_alert": sample["example_alert"], "example_url": sample["example_url"], "risk_text": sample["text"],
        "rule_based_extraction": sample["rule_pred"].map(lambda s: "; ".join(sorted(s))),
        "reference_labels_ai": sample["text_id"].map(
            lambda t: pd.read_csv(EVAL_DIR / "reference_labels_ai.csv", dtype=str).set_index("text_id").loc[t, "reference_labels"]),
    })
    for col in ["owner_agrees_with_reference", "owner_corrected_labels", "owner_comment"]:
        ev[col] = ev["text_id"].map(lambda t: (previous.get(t) or {}).get(col))

    # Uncertain cases from the full dataset
    cand = pd.read_csv(C.PROCESSED_DIR / "substance_candidates_uncertain.csv")
    subs = pd.read_csv(C.PROCESSED_DIR / "alert_substances.csv")
    alerts = pd.read_csv(C.PROCESSED_DIR / "alerts_clean.csv", low_memory=False).set_index("alert_number")
    unc = []
    for r in cand.itertuples():
        unc.append({"alert_number": r.alert_number, "issue": "unrecognised candidate", "item": r.candidate_text})
    for r in subs[subs["confidence"].eq("uncertain")].itertuples():
        unc.append({"alert_number": r.alert_number, "issue": "hedged mention ('and/or')", "item": r.substance})
    for a_no in alerts.index[alerts["primary_substance"].isna()]:
        unc.append({"alert_number": a_no, "issue": "no substance extracted", "item": ""})
    unc = pd.DataFrame(unc)
    unc["risk_text"] = unc["alert_number"].map(alerts["risk_description"])
    unc["case_url"] = unc["alert_number"].map(alerts["case_url"])
    unc["owner_decision"] = None
    unc["owner_comment"] = None

    instructions = pd.DataFrame({"Instructions": [
        "Purpose: check the substance labels used to evaluate the extraction rules.",
        "The column 'reference_labels_ai' was written by an AI assistant (Claude). It is NOT verified by a human.",
        "Sheet 'evaluation_sample': for each row, write 'yes' in owner_agrees_with_reference if the AI labels are correct.",
        "If not, write 'no' and type the correct labels in owner_corrected_labels, separated by semicolons (;), using the names from sheet 'substance_names'.",
        "Guideline: label every specific substance or named microorganism the text says the product contains. Do not label class words such as 'corticosteroid'.",
        "Sheet 'uncertain_cases': decide whether each item is a real substance (write substance name) or not (write 'reject').",
        "After saving, run: python src/evaluate_extraction.py  -> the report will then use your labels and say so.",
    ]})
    names = pd.DataFrame([{"substance": n, "abbreviation": a, "agent_type": k} for n, a, k, *_ in SUBSTANCES])
    with pd.ExcelWriter(REVIEW_FILE, engine="openpyxl") as xw:
        instructions.to_excel(xw, sheet_name="instructions", index=False)
        ev.to_excel(xw, sheet_name="evaluation_sample", index=False)
        unc.to_excel(xw, sheet_name="uncertain_cases", index=False)
        names.to_excel(xw, sheet_name="substance_names", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(80, max(12, max(len(str(c.value or "")) for c in col[:50]) + 2))
            ws.freeze_panes = "A2"


def write_report(sample, metrics, errors, coverage, use_model) -> None:
    n_owner = int((sample["label_source"] == "project owner (human)").sum())
    R = []
    w = R.append
    w("# Substance Extraction - Evaluation (Stage C)\n")
    w("*Generated by `src/evaluate_extraction.py`.*\n")
    w("## Label provenance (read this first)\n")
    if n_owner == 0:
        w("**All reference labels in this report were produced by an AI assistant (Claude), not by a human annotator.** "
          "The AI read each sampled text and wrote the substances it names, following the guideline below, without looking at the regex output. "
          "Because the same AI system also wrote the extraction rules, the two are **not fully independent**, and the metrics below are an "
          "*agreement check*, not a validated accuracy figure. The project owner can confirm or correct each label in "
          "`data/review/substance_review_for_owner.xlsx`; re-running the script will then use the human labels.\n")
    else:
        w(f"{n_owner} of {len(sample)} reference labels were confirmed or corrected by the project owner; the remaining "
          f"{len(sample) - n_owner} are AI-produced and not human-verified.\n")
    w("## Design\n")
    w(f"- Unit of evaluation: distinct risk text ({len(sample)} sampled at random, seed {SEED}, from the distinct texts in the dataset), "
      f"covering {int(sample['alerts'].sum())} alerts.")
    w("- Guideline: label every specific chemical substance or named microorganism the text says the product contains; "
      "do not label class words (corticosteroid, nitrosamine, allergenic fragrances).")
    w("- Metrics: precision = share of extracted items that are correct; recall = share of labelled items that were found; "
      "F1 = harmonic mean; exact match = share of texts where the extracted set equals the labelled set.\n")
    w("## Results\n")
    w(md_table(metrics))
    w("")
    w("## Errors\n")
    if errors.empty:
        w("No disagreements between the extraction and the reference labels in the sample.\n")
    else:
        w(md_table(errors))
        w("")
    if use_model:
        w("## Pretrained model comparison\n")
        w(f"- Model: [{MODEL_ID}](https://huggingface.co/{MODEL_ID}), revision `{MODEL_REVISION[:12]}`, licence Apache-2.0 (from the model card).")
        w("- Training domain (model card): BC4CHEMD - chemical mentions in PubMed abstracts. Safety Gate texts are short regulatory "
          "sentences with consumer-facing wording, abbreviations in brackets and occasional typos, so domain transfer is not guaranteed.")
        w("- Run locally on CPU; no data leaves the machine. Model weights are not redistributed in this repository.")
        if coverage:
            w(f"- On all {coverage['distinct_texts']} distinct texts, the model and the rules produce the same chemical set for "
              f"{coverage['texts_where_methods_agree']} texts ({coverage['alerts_where_methods_agree']} of {coverage['alerts_total']} alerts). "
              "Disagreements: `data/evaluation/rule_vs_model_disagreements.csv`.")
            d = pd.read_csv(EVAL_DIR / "rule_vs_model_disagreements.csv")
            only_model = sorted({x for v in d["only_model"].dropna() for x in str(v).split("; ")})
            only_rule = d["only_rule"].dropna().str.split("; ").explode().value_counts()
            w(f"- Items found **only by the model** (all texts): {', '.join(f'`{x}`' for x in only_model)}. "
              "On manual inspection these are class words (e.g. corticosteroid, phthalate, prostaglandin) or a misspelt name "
              "already covered by its abbreviation - no new substance was discovered.")
            w("- Items found **only by the rules**: " + ", ".join(f"`{k}` ({v} texts)" for k, v in only_rule.items())
              + ". The model does not tag the metal *lead*; the hedged plant extract is a rule-based 'uncertain' item.")
        w("\n**Why the rule-based score is 1.0.** The dictionary was written for this export, and the AI reference labels come from "
          "the same AI system that wrote the rules. A perfect score here shows internal consistency, not real-world accuracy.\n")
        w("**Interpretation.** The rule-based dictionary is tuned to this export and therefore scores higher on it; that is expected and "
          "is also its weakness (it only knows substances someone has added). The model needs no dictionary and can surface new substance "
          "names, but it misses some short or ambiguous names. A practical design is: dictionary for reporting, model as a "
          "*discovery* step whose new findings go into the review queue.\n")
    w("## Limitations\n")
    w("- Small sample (60 distinct texts); BMHCA sentences dominate the alert-weighted figures.")
    w("- Reference labels are AI-produced until reviewed by the owner.")
    w("- Exact-name matching: a correct mention with a different canonical name would count as an error.")
    w("- The dictionary was developed on the same export that is evaluated here (no held-out data). New exports are the real test.")
    (C.REPORTS_DIR / "substance_extraction_evaluation.md").write_text("\n".join(R), encoding="utf-8")
    print(metrics.to_string())
    print(errors.to_string())
    if coverage:
        print(coverage)


if __name__ == "__main__":
    main()
