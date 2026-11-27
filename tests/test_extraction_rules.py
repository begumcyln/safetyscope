"""Unit tests for parsing and extraction rules, using short hand-written examples."""

from safetyscope.measures import parse_measures
from safetyscope.standardize import brand_key, product_group, standardize_product
from safetyscope.substances import extract_candidates, extract_mentions, text_flags


def names(text):
    return [m.substance for m in extract_mentions(text)]


def test_bmhca_variants():
    for t in ["contains 2-(4-tert-butylbenzyl) propionaldehyde (BMHCA), which",
              "contains 2-(4-tert- butylbenzyl) propionaldehyde (BMHCA)",
              "contains \n2-(4-tert-butylbenzyl)propionaldehyde"]:
        assert names(t) == ["Butylphenyl methylpropional"]


def test_multiple_substances_in_order():
    t = ("The product contains 2-hydroxyethyl methacrylate (HEMA) and p-hydroxyanisole (mequinol) "
         "which are prohibited in nail products for consumer use.")
    assert names(t) == ["2-Hydroxyethyl methacrylate", "Mequinol (p-hydroxyanisole)"]


def test_lead_verb_is_not_a_substance():
    assert names("Exposure to it could cause skin irritation and may lead to endocrine problems.") == []
    assert names("The product contains lead (measured value: 0.06 %).") == ["Lead"]


def test_hydroquinone_vs_mequinol():
    assert names("contains hydroquinone methylether (mequinol)") == ["Mequinol (p-hydroxyanisole)"]
    assert names("The product contains hydroquinone, which is prohibited") == ["Hydroquinone"]


def test_mi_not_confused_with_mci():
    assert names("the preservative methylchloroisothiazolinone (MCI)") == ["Methylchloroisothiazolinone"]
    assert set(names("methylchloroisothiazolinone (MCI) and methylisothiazolinonev (MI)")) == {
        "Methylchloroisothiazolinone", "Methylisothiazolinone"}


def test_colour_index_with_lowercase_l_typo():
    assert "CI 45160" in names("The product contains dyes CI 45170, Cl 45160 and Basic Yellow 40")


def test_hedged_mention_is_uncertain():
    found = extract_mentions("Certain ingredients (Centella Asiatica and/or Bakuchiol extracts) may cause irritation.")
    assert {m.confidence for m in found} == {"uncertain"}


def test_unknown_substance_becomes_candidate():
    text = "The product contains zinc pyrithione, which is prohibited in cosmetic products."
    found = extract_mentions(text)
    assert found == []
    assert extract_candidates(text, found) == ["zinc pyrithione"]


def test_no_mentions_for_non_substance_risk():
    assert names("The sun protection factor of the product is too low (measured value 2.2).") == []


def test_text_flags():
    f = text_flags("According to the list of ingredients, the product contains X, which is prohibited in cosmetic products.")
    assert f["alert_states_prohibited"] and f["based_on_ingredient_list"] and not f["has_measured_value"]


def test_parse_multiple_measures():
    text = ("Type of economic operator taking notified measure(s): Distributor\nCategory of measure(s): Stop of sales\n"
            "Date of entry into force: 20/10/2025\n\nType of economic operator taking notified measure(s): Distributor\n"
            "Category of measure(s): Removal of this product listing by the online marketplace\nDate of entry into force: Unknown")
    rows = parse_measures(text, "voluntary")
    assert len(rows) == 2
    assert rows[0]["entry_into_force_date"].strftime("%Y-%m-%d") == "2025-10-20"
    assert rows[1]["entry_into_force_raw"] == "Unknown" and str(rows[1]["entry_into_force_date"]) == "NaT"


def test_product_standardisation():
    assert standardize_product(" Aftershave") == standardize_product("After-shave") == "Aftershave"
    assert standardize_product("shower gel") == "Shower gel"
    assert product_group("Eau de toilette") == "Fragrance"
    assert product_group("Skin lightening cream") == "Skin lightening"
    assert product_group("Perfume set") == "Sets & kits"


def test_brand_key():
    assert brand_key("PARFUMS DE QUALITE'") == brand_key("Parfums de Qualité")
    assert brand_key("Unknown") is None
    assert brand_key("L'OREAL PARIS") != brand_key("Loreal")
