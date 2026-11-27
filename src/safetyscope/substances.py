"""Rule-based extraction of hazardous agents from the Safety Gate 'Risk' text.

Approach (interpretable baseline)
---------------------------------
1. Normalise the text (whitespace, known typos such as "tert- butyl").
2. Match a curated dictionary of substances and their aliases with regular
   expressions. A dictionary match is a *confirmed mention*: the substance name
   literally appears in the alert text.
3. Run a generic "contains <X>" candidate pattern. Candidates that are not in
   the dictionary are returned as *uncertain* so a person can review them.

What a match means
------------------
A mention means "the Safety Gate alert text names this substance". It does
NOT mean the project has verified the substance's legal status. Phrases such
as "prohibited in cosmetic products" are captured as the *alert's* wording
(field ``alert_states_prohibited``), attributed to Safety Gate.

CAS numbers
-----------
The Safety Gate texts in this export contain no CAS numbers (checked with a
CAS regex, see reports). CAS numbers in this dictionary are reference data
added by the project and cross-checked against PubChem synonyms
(``src/verify_cas.py``, results in data/reference/cas_verification.csv).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# (canonical name, abbreviation, agent type, substance group, alias regexes, CAS)
# Alias regexes are applied case-insensitively unless marked with (?-i:...)
SUBSTANCES = [
    ("Butylphenyl methylpropional", "BMHCA", "chemical", "Fragrance ingredient (CMR)",
     [r"2-\(4-tert-butylbenzyl\)\s?propionaldehyde", r"butylphenyl methylpropional", r"(?-i:\bBMHCA\b)", r"\blilial\b"], "80-54-6"),
    ("Diphenyl(2,4,6-trimethylbenzoyl)phosphine oxide", "TPO", "chemical", "Photoinitiator (nail products)",
     [r"diphenyl\s?\(2,4,6-trimethylbenzoyl\)\s?phosphine oxide", r"trimethylbenzoyl diphenylphosphine oxide", r"(?-i:\bTPO\b)"], "75980-60-8"),
    ("Hydroxyisohexyl 3-cyclohexene carboxaldehyde", "HICC", "chemical", "Fragrance allergen",
     [r"hydroxyisohexyl 3-cyclohexene carboxaldehyde", r"(?-i:\bHICC\b)"], "31906-04-4"),
    ("Trimethylolpropane triacrylate", "TMPTA", "chemical", "Acrylate (nail products)",
     [r"trimethylolpropane triacrylate", r"(?-i:\bTMPTA\b)"], "15625-89-5"),
    ("2-Hydroxyethyl methacrylate", "HEMA", "chemical", "Acrylate (nail products)",
     [r"2-hydroxyethyl methacrylate", r"(?-i:\bHEMA\b)"], "868-77-9"),
    ("Mequinol (p-hydroxyanisole)", "Mequinol", "chemical", "Other restricted ingredient",
     [r"\bmequinol\b", r"p-hydroxyanisole", r"hydroquinone methyl ?ether"], "150-76-5"),
    ("Hydroquinone", None, "chemical", "Skin-lightening agent",
     [r"\bhydroquinone\b(?! methyl ?ether)"], "123-31-9"),
    ("Clobetasol propionate", None, "chemical", "Corticosteroid",
     [r"clobetasol propionate"], "25122-46-7"),
    ("Mercury", None, "chemical", "Heavy metal / element",
     [r"\bmercury\b"], "7439-97-6"),
    # "lead" is also an English verb ("may lead to"); exclude that use.
    ("Lead", None, "chemical", "Heavy metal / element",
     [r"\blead\b(?!\s+to\b)"], "7439-92-1"),
    ("Arsenic", None, "chemical", "Heavy metal / element", [r"\barsenic\b"], "7440-38-2"),
    ("Antimony", None, "chemical", "Heavy metal / element", [r"\bantimony\b"], "7440-36-0"),
    ("Selenium", None, "chemical", "Heavy metal / element", [r"\bselenium\b"], "7782-49-2"),
    ("Barium", None, "chemical", "Heavy metal / element", [r"\bbarium\b"], "7440-39-3"),
    ("Cobalt", None, "chemical", "Heavy metal / element", [r"\bcobalt\b"], "7440-48-4"),
    ("Zirconium", None, "chemical", "Heavy metal / element", [r"\bzirconium\b"], "7440-67-7"),
    ("Nickel", None, "chemical", "Heavy metal / element", [r"\bnickel\b"], "7440-02-0"),
    ("Methylisothiazolinone", "MI", "chemical", "Preservative",
     [r"(?<!chloro)methylisothiazolinonev?\b", r"(?-i:\(MI\))"], "2682-20-4"),
    ("Methylchloroisothiazolinone", "MCI", "chemical", "Preservative",
     [r"methylchloroisothiazolinone", r"(?-i:\bMCI\b)"], "26172-55-4"),
    ("Formaldehyde", None, "chemical", "Preservative", [r"\bformaldehyde\b"], "50-00-0"),
    ("Isobutylparaben", None, "chemical", "Preservative", [r"isobutylparaben"], "4247-02-3"),
    ("Octamethylcyclotetrasiloxane", "D4", "chemical", "Silicone",
     [r"octamethylcyclotetrasiloxane", r"(?-i:\(D4\))"], "556-67-2"),
    ("Dibutyl phthalate", "DBP", "chemical", "Phthalate", [r"dibutyl phthalate", r"(?-i:\bDBP\b)"], "84-74-2"),
    ("Benzophenone", None, "chemical", "UV absorber / other", [r"\bbenzophenone\b"], "119-61-9"),
    ("N-Nitrosodiethanolamine", "NDELA", "chemical", "Nitrosamine",
     [r"n-nitrosodiethanolamine", r"(?-i:\bNDELA\b)"], "1116-54-7"),
    ("N-Nitrosodibutylamine", "NDBA", "chemical", "Nitrosamine",
     [r"n-nitrosodibutylamine", r"(?-i:\bNDBA\b)"], "924-16-3"),
    ("Trisodium nitrilotriacetate", None, "chemical", "Other restricted ingredient",
     [r"trisodium nitrilotriacetate"], "5064-31-3"),
    ("Hydrogen peroxide", None, "chemical", "Oxidising / bleaching agent", [r"hydrogen peroxide"], "7722-84-1"),
    ("Benzoyl peroxide", None, "chemical", "Oxidising / bleaching agent", [r"benzoyl peroxide"], "94-36-0"),
    ("Thioglycolic acid", None, "chemical", "Other restricted ingredient", [r"thioglycolic acid"], "68-11-1"),
    ("Glyoxylic acid", None, "chemical", "Other restricted ingredient", [r"glyoxylic acid"], "298-12-4"),
    ("Phenol", None, "chemical", "Other restricted ingredient", [r"\bphenol\b"], "108-95-2"),
    ("Estragole", None, "chemical", "Fragrance ingredient", [r"\bestragole\b"], "140-67-0"),
    ("Citral", None, "chemical", "Fragrance allergen", [r"\bcitral\b"], "5392-40-5"),
    ("Benzyl alcohol", None, "chemical", "Fragrance allergen", [r"benzyl alcohol"], "100-51-6"),
    ("Limonene", None, "chemical", "Fragrance allergen", [r"\b(?:d-)?limonene\b"], "5989-27-5"),
    ("Linalool", None, "chemical", "Fragrance allergen", [r"\blinalool\b"], "78-70-6"),
    ("Citronellol", None, "chemical", "Fragrance allergen", [r"\bcitronellol\b"], "106-22-9"),
    ("Geraniol", None, "chemical", "Fragrance allergen", [r"\bgeraniol\b"], "106-24-1"),
    ("Eugenol", None, "chemical", "Fragrance allergen", [r"(?<!iso)\beugenol\b"], "97-53-0"),
    ("Isoeugenol", None, "chemical", "Fragrance allergen", [r"\bisoeugenol\b"], "97-54-1"),
    ("Hexyl cinnamal", None, "chemical", "Fragrance allergen", [r"hexyl cinnamal"], "101-86-0"),
    ("Coumarin", None, "chemical", "Fragrance allergen", [r"\bcoumarin\b"], "91-64-5"),
    ("Alpha-isomethyl ionone", None, "chemical", "Fragrance allergen", [r"alpha-isomethyl ionone"], "127-51-5"),
    ("Bimatoprost", None, "chemical", "Prostaglandin analogue", [r"\bbimatoprost\b"], "155206-00-1"),
    ("Cloprostenol isopropyl ester", None, "chemical", "Prostaglandin analogue",
     [r"cloprostenol isopropyl ester"], "157283-66-4"),
    ("Delta-9-tetrahydrocannabinol", "THC", "chemical", "Other restricted ingredient",
     [r"delta-9-tetrahydrocannabinol"], "1972-08-3"),
    ("Carbon black (nano)", "CI 77266", "chemical", "Colorant", [r"carbon black", r"\bCI 77266\b"], "1333-86-4"),
    ("Ethylhexyl methoxycinnamate", None, "chemical", "UV filter", [r"ethylhexyl methoxycinnamate"], "5466-77-3"),
    ("Padimate O", None, "chemical", "UV filter", [r"padimate-?o\b"], "21245-02-3"),
    # Colorants are named by Colour Index (CI) number in the texts. CAS numbers
    # are not added for these because CI-to-CAS mapping is ambiguous for salts.
    ("CI 45160", None, "chemical", "Colorant", [r"\bC[Il] 45160\b"], None),
    ("CI 45170", None, "chemical", "Colorant", [r"\bC[Il] 45170\b"], None),
    ("CI 45174", None, "chemical", "Colorant", [r"\bC[Il] 45174\b"], None),
    ("Solvent Yellow 172", None, "chemical", "Colorant", [r"solvent yellow 172"], None),
    ("Basic Yellow 40", None, "chemical", "Colorant", [r"basic yellow 40"], None),
    # Microorganisms (microbiological contamination alerts)
    ("Pseudomonas aeruginosa", None, "microorganism", "Bacteria", [r"pseudomonas aeruginosa"], None),
    ("Staphylococcus aureus", None, "microorganism", "Bacteria", [r"staphylococcus aureus"], None),
    ("Burkholderia cepacia", None, "microorganism", "Bacteria", [r"bur(?:k)?holderia cepacia"], None),
    ("Pluralibacter gergoviae", None, "microorganism", "Bacteria", [r"pluralibacter gergoviae"], None),
    ("Gluconacetobacter liquefaciens", None, "microorganism", "Bacteria", [r"gluconacetobacter liquefaciens"], None),
    ("Paenibacillus glucanolyticus", None, "microorganism", "Bacteria", [r"paenibacillus glucanolyticus"], None),
    ("Candida parapsilosis", None, "microorganism", "Yeast", [r"candida parapsilosis"], None),
    ("Aspergillus versicolor", None, "microorganism", "Mould", [r"aspergillus versicolor"], None),
    ("Yeast (unspecified)", None, "microorganism", "Yeast", [r"contaminated with yeast", r"\byeast and\b"], None),
    # The alert text hedges ("Centella Asiatica and/or Bakuchiol extracts"), so
    # these are always reported as uncertain (see UNCERTAIN_BY_DEFAULT).
    ("Centella asiatica extract", None, "chemical", "Plant extract", [r"centella asiatica"], None),
    ("Bakuchiol", None, "chemical", "Plant extract", [r"\bbakuchiol\b"], None),
    ("Aerobic mesophilic microorganisms (unspecified)", None, "microorganism", "Total aerobic count",
     [r"(?:aerobic mesophilic|mesophilic aerobic|aerobic) (?:bacteria|microorganisms)(?! (?:pluralibacter|burholderia|burkholderia))",
      r"excessive amount of aerobic mesophilic bacteria"], None),
]

# Generic pattern used only to *find candidates* the dictionary may have missed.
CANDIDATE_RE = re.compile(
    r"(?:contains?|concentration of|contaminated with|ingredients \()\s+(?:the |an? |a mixture of the )?"
    r"(?:preservatives? |allergenic fragrances? |active substance |colorants |dyes |UV filters,? )?"
    r"(?P<cand>[A-Za-z0-9][\w\-\(\), ]{2,80}?)(?=[\.,;]|\s\(|\swhich|\sthat|\sand\s|$)",
    re.I,
)
CANDIDATE_STOPWORDS = {
    "the product", "product", "list of ingredients", "excessive concentration", "excessive amount",
    "mixture", "the list of ingredients", "allergenic fragrances",
}
UNCERTAIN_BY_DEFAULT = {"Centella asiatica extract", "Bakuchiol"}

PROHIBITION_RE = re.compile(r"\b(?:prohibited|forbidden|banned)\b", re.I)
MEASURED_RE = re.compile(r"measured value", re.I)
UNDECLARED_RE = re.compile(r"not (?:mentioned|indicated) in the list of ingredients|presence is not indicated", re.I)
INGREDIENT_LIST_RE = re.compile(r"according to the (?:list of ingredients|ingredients list)", re.I)
CAS_RE = re.compile(r"\b\d{2,7}-\d{2}-\d\b")


@dataclass
class Mention:
    substance: str
    abbreviation: str | None
    agent_type: str
    substance_group: str
    cas_number: str | None
    matched_text: str
    start: int
    method: str = "dictionary"
    confidence: str = "confirmed"


_COMPILED = [
    (name, abbr, kind, group, cas, [re.compile(p, re.I) for p in patterns])
    for name, abbr, kind, group, patterns, cas in SUBSTANCES
]


def normalize_risk_text(text: str | None) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", str(text)).strip()
    t = re.sub(r"tert-\s+butyl", "tert-butyl", t)  # "2-(4-tert- butylbenzyl)" typo variant
    t = t.replace("0. 0", "0.0")  # "0. 023%" spacing typo in measured values
    return t


def extract_mentions(text: str | None) -> list[Mention]:
    """Return one Mention per distinct substance found in the text (dictionary step)."""
    t = normalize_risk_text(text)
    found: dict[str, Mention] = {}
    for name, abbr, kind, group, cas, patterns in _COMPILED:
        for pattern in patterns:
            m = pattern.search(t)
            if m and (name not in found or m.start() < found[name].start):
                conf = "uncertain" if name in UNCERTAIN_BY_DEFAULT else "confirmed"
                found[name] = Mention(name, abbr, kind, group, cas, m.group(0), m.start(), confidence=conf)
    return sorted(found.values(), key=lambda m: m.start)


def _dictionary_spans(t: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for *_, pats in _COMPILED for p in pats for m in p.finditer(t)]


def extract_candidates(text: str | None, known: list[Mention]) -> list[str]:
    """Generic-pattern candidates not covered by any dictionary match -> 'uncertain'."""
    t = normalize_risk_text(text)
    spans = _dictionary_spans(t)
    out = []
    for m in CANDIDATE_RE.finditer(t):
        cand = m.group("cand").strip(" ,()")
        low = cand.lower()
        if low in CANDIDATE_STOPWORDS or len(low) < 3:
            continue
        start, end = m.start("cand"), m.end("cand")
        # Skip if the candidate overlaps a dictionary match or is directly
        # followed by one, e.g. a misspelt name followed by "(BMHCA)".
        if any(s0 < end + 3 and start < s1 for s0, s1 in spans):
            continue
        out.append(cand)
    return out


def text_flags(text: str | None) -> dict:
    t = normalize_risk_text(text)
    return {
        "alert_states_prohibited": bool(PROHIBITION_RE.search(t)),
        "has_measured_value": bool(MEASURED_RE.search(t)),
        "undeclared_ingredient": bool(UNDECLARED_RE.search(t)),
        "based_on_ingredient_list": bool(INGREDIENT_LIST_RE.search(t)),
        "cas_number_in_text": bool(CAS_RE.search(t)),
    }


def dictionary_table():
    """Dictionary as rows (for export / database)."""
    return [
        {"substance": n, "abbreviation": a, "agent_type": k, "substance_group": g,
         "cas_number": c, "alias_patterns": " || ".join(p)}
        for n, a, k, g, p, c in SUBSTANCES
    ]
