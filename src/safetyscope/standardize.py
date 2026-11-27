"""Reference mappings used to standardise names.

Every mapping here is explicit and reviewable. Values not listed are kept as
they are (after whitespace normalisation). The mappings are also exported to
data/reference/ so they can be reviewed without reading code.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def normalize_text(value) -> str | None:
    """Unicode NFC, replace non-breaking/odd spaces, collapse whitespace, strip."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = unicodedata.normalize("NFC", str(value))
    text = text.replace(" ", " ").replace(" ", " ").replace("​", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


# ---------------------------------------------------------------------------
# Countries
# ---------------------------------------------------------------------------
# Safety Gate uses its own country labels. We keep the original label and add
# a short display name and ISO 3166-1 alpha-2 code. "Unknown" is a genuine
# Safety Gate value meaning the origin was not established; it is kept as a
# category (not converted to missing) because it carries meaning.

COUNTRY_MAP = {
    # label in export: (display name, ISO2, EU/EEA member flag)
    "Australia": ("Australia", "AU", False),
    "Austria": ("Austria", "AT", True),
    "Belgium": ("Belgium", "BE", True),
    "Bosnia and Herzegovina": ("Bosnia and Herzegovina", "BA", False),
    "Brazil": ("Brazil", "BR", False),
    "Bulgaria": ("Bulgaria", "BG", True),
    "Cambodia": ("Cambodia", "KH", False),
    "Cameroon": ("Cameroon", "CM", False),
    "Canada": ("Canada", "CA", False),
    "Congo": ("Congo", "CG", False),
    "Croatia": ("Croatia", "HR", True),
    "Cyprus": ("Cyprus", "CY", True),
    "Czechia": ("Czechia", "CZ", True),
    "Democratic Republic Of Congo": ("DR Congo", "CD", False),
    "Egypt": ("Egypt", "EG", False),
    "Estonia": ("Estonia", "EE", True),
    "Finland": ("Finland", "FI", True),
    "France": ("France", "FR", True),
    "Germany": ("Germany", "DE", True),
    "Ghana": ("Ghana", "GH", False),
    "Greece": ("Greece", "GR", True),
    "Hungary": ("Hungary", "HU", True),
    "India": ("India", "IN", False),
    "Ireland": ("Ireland", "IE", True),
    "Israel": ("Israel", "IL", False),
    "Italy": ("Italy", "IT", True),
    "Ivory Coast": ("Côte d'Ivoire", "CI", False),
    "Japan": ("Japan", "JP", False),
    "Lithuania": ("Lithuania", "LT", True),
    "Luxembourg": ("Luxembourg", "LU", True),
    "Malta": ("Malta", "MT", True),
    "Morocco": ("Morocco", "MA", False),
    "Pakistan": ("Pakistan", "PK", False),
    "People's Republic of China": ("China", "CN", False),
    "Peru": ("Peru", "PE", False),
    "Poland": ("Poland", "PL", True),
    "Portugal": ("Portugal", "PT", True),
    "Republic of Korea": ("South Korea", "KR", False),
    "San Marino": ("San Marino", "SM", False),
    "Senegal": ("Senegal", "SN", False),
    "Slovakia": ("Slovakia", "SK", True),
    "Slovenia": ("Slovenia", "SI", True),
    "Spain": ("Spain", "ES", True),
    "Sweden": ("Sweden", "SE", True),
    "Switzerland": ("Switzerland", "CH", False),
    "Syria": ("Syria", "SY", False),
    "Thailand": ("Thailand", "TH", False),
    "The Netherlands": ("Netherlands", "NL", True),
    "Togo": ("Togo", "TG", False),
    "Tunisia": ("Tunisia", "TN", False),
    "Türkiye": ("Türkiye", "TR", False),
    "Ukraine": ("Ukraine", "UA", False),
    "United Arab Emirates": ("United Arab Emirates", "AE", False),
    "United Kingdom": ("United Kingdom", "GB", False),
    # Northern Ireland participates in Safety Gate under the Windsor Framework.
    "United Kingdom in respect of Northern Ireland": ("UK (Northern Ireland)", "XI", False),
    "United States": ("United States", "US", False),
    "Unknown": ("Unknown", None, None),
}


def country_display(label: str | None) -> str | None:
    if label is None:
        return None
    return COUNTRY_MAP.get(label, (label, None, None))[0]


def country_iso2(label: str | None) -> str | None:
    if label is None:
        return None
    return COUNTRY_MAP.get(label, (label, None, None))[1]


def is_eu_member(label: str | None):
    if label is None:
        return None
    return COUNTRY_MAP.get(label, (label, None, None))[2]


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
# Step 1: spelling/format variants -> one standard product name.
PRODUCT_VARIANTS = {
    "eau  de toilette": "eau de toilette",
    "parfume": "perfume",
    "parfum": "perfume",
    "perfumes set": "perfume set",
    "after-shave": "aftershave",
    "skin-lightening cream": "skin lightening cream",
    "nails gel": "nail gel",
    "hair spray": "hairspray",
    "sun screen": "sunscreen",
    "hair-care product": "hair care product",
    "haircare product": "hair care product",
    "bodywash": "body wash",
    "nail varnish": "nail polish",
    "gel nail varnish": "gel nail polish",
    "nail gel polish": "gel nail polish",
    "uv gel nail polish": "gel nail polish",
    "dark spots corrector": "dark spot corrector",
    "hair colour mousse": "hair colouring mousse",
    "children’s perfume": "children's perfume",
}

# Step 2: keyword rules -> analytical product group (first match wins).
# This grouping is a project-defined analytical aid, NOT a Safety Gate field.
PRODUCT_GROUP_RULES = [
    ("Skin lightening", r"lightening|dark spot"),
    ("Fragrance", r"perfume|parfum|toilette|cologne|aftershave|body fragrance|body mist|body water|body spray"),
    ("Deodorant", r"deodorant"),
    ("Nail products", r"nail"),
    ("Hair dye & colouring", r"hair dye|hair colou?r|henna"),
    ("Sun & tanning", r"sun|tanning|spf"),
    ("Hair care & styling", r"hair|shampoo|beard|brow lamination"),
    ("Eye & lash products", r"eyelash|eyebrow|eyeliner|eyeshadow|eye "),
    ("Make-up & face paint", r"make-up|foundation|concealer|face paint"),
    ("Oral care", r"tooth|teeth"),
    ("Bath, shower & soap", r"shower|bath|soap|wash|foam|sanitiser|wipes|footbath"),
    ("Skin care", r"cream|lotion|serum|oil|butter|milk|gel|mask|tonic|toner|scrub|powder|moisturi|ointment|micellar|conditioner|mousse"),
]


def standardize_product(value: str | None) -> str | None:
    text = normalize_text(value)
    if text is None:
        return None
    key = text.lower()
    key = PRODUCT_VARIANTS.get(key, key)
    return key[:1].upper() + key[1:]


def product_group(std_name: str | None) -> str:
    if not std_name:
        return "Other"
    name = std_name.lower()
    if "set" in name.split() or name.endswith(" kit") or name == "cosmetic products":
        return "Sets & kits"
    for group, pattern in PRODUCT_GROUP_RULES:
        if re.search(pattern, name):
            return group
    return "Other"


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------

def brand_key(value: str | None) -> str | None:
    """Matching key: case-insensitive, accents and punctuation ignored."""
    text = normalize_text(value)
    if text is None:
        return None
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s&]", " ", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    if text in {"unknown", "n a", "na", "none", "no brand", "without brand", "not specified"}:
        return None
    return text or None


def brand_display_names(raw: pd.Series) -> pd.Series:
    """For each brand key, pick the most frequent original spelling as display name."""
    clean = raw.map(normalize_text)
    keys = raw.map(brand_key)
    frame = pd.DataFrame({"key": keys, "clean": clean}).dropna()
    best = (
        frame.groupby(["key", "clean"]).size().reset_index(name="n")
        .sort_values(["key", "n", "clean"], ascending=[True, False, True])
        .drop_duplicates("key").set_index("key")["clean"]
    )
    return keys.map(best)
