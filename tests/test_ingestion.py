"""Offline tests for the Safety Gate XML ingestion (no network access).

The XML fixture below is a synthetic, minimal example written for testing
(invented alert numbers); it only mimics the structure of an official report.
"""

import update_from_api as U
from safetyscope.measures import parse_measures
from safetyscope.safety_gate_api import parse_report

FIXTURE = """<?xml version="1.0" encoding="UTF-8"?><Safety-Gate>
<report_language>en</report_language><report_date>05/12/2026</report_date><report_year>2026</report_year><report_week>48</report_week>
<notifications><caseNumber>SR/99001/26</caseNumber><publicationDate>01-12-2026</publicationDate>
<reference>https://ec.europa.eu/safety-gate-alerts/screen/webReport/alertDetail/1</reference><category>Cosmetics</category>
<product>Perfume</product><brand>TestBrand</brand><name>Test</name><riskType>Chemical</riskType>
<danger>The product contains lead (measured value: 1 mg/kg).</danger>
<measures>Type of economic operator to whom the measure(s) were ordered: DistributorCategory of measure(s): Ban on the marketing of the product and any accompanying measuresDate of entry into force: 10/11/2026Type of economic operator taking notified measure(s): ImporterCategory of measure(s): Stop of salesDate of entry into force: Unknown</measures>
<notifyingCountry>Italy</notifyingCountry><countryOfOrigin>Unknown</countryOfOrigin><type>Consumer</type><level>Serious risk</level></notifications>
<notifications><caseNumber>SR/99002/26</caseNumber><publicationDate>02-12-2026</publicationDate><category>Toys</category>
<product>Doll</product><riskType>Chemical</riskType><notifyingCountry>Spain</notifyingCountry><type>Consumer</type><level>Serious risk</level></notifications>
</Safety-Gate>"""


def test_parse_report(tmp_path):
    path = tmp_path / "Report-2026-48.xml"
    path.write_text(FIXTURE, encoding="utf-8")
    df = parse_report(path)
    assert len(df) == 2
    assert df.loc[0, "caseNumber"] == "SR/99001/26"
    assert df.loc[0, "report_reference"] == "Report-2026-48"
    assert df.loc[1, "category"] == "Toys"


def test_split_measures_rebuilds_export_layout():
    xml_text = ("Type of economic operator to whom the measure(s) were ordered: DistributorCategory of measure(s): "
                "Ban on the marketing of the product and any accompanying measuresDate of entry into force: 10/11/2026"
                "Type of economic operator taking notified measure(s): ImporterCategory of measure(s): Stop of sales"
                "Date of entry into force: Unknown")
    comp, vol = U.split_measures(xml_text)
    c = parse_measures(comp, "compulsory")
    v = parse_measures(vol, "voluntary")
    assert len(c) == 1 and c[0]["measure_category"].startswith("Ban on the marketing")
    assert c[0]["entry_into_force_date"].strftime("%Y-%m-%d") == "2026-11-10"
    assert len(v) == 1 and v[0]["measure_category"] == "Stop of sales" and v[0]["entry_into_force_raw"] == "Unknown"
    assert U.split_measures(None) == (None, None)


def test_export_like_file_is_readable_by_pipeline(tmp_path):
    from safetyscope.extract import read_export
    path = tmp_path / "report.xml"
    path.write_text(FIXTURE, encoding="utf-8")
    x = parse_report(path)
    cos = x[x["category"].eq("Cosmetics")]
    out = tmp_path / "api.xlsx"
    U.write_export_like(U.to_export_layout(cos), out)
    df = read_export(out)
    assert list(df["Alert number"]) == ["SR/99001/26"]
    assert df.loc[0, "Category"] == "Cosmetics"
    assert "Ban on the marketing" in df.loc[0, "Compulsory measures"]


def test_duplicate_prevention_uses_existing_alerts():
    known = U.known_alert_numbers()
    assert "SR/01834/25" in known  # an alert from the original export
    assert "SR/99001/26" not in known
