"""Checks on the generated Power BI assets (run src/build_powerbi.py first)."""

import json
import re

import pandas as pd
import pytest

from safetyscope import config as C

PBI = C.POWERBI_DIR


@pytest.fixture(scope="module", autouse=True)
def _needs_assets():
    if not (PBI / "pbip" / "SafetyScope.pbip").exists():
        pytest.skip("Run `python src/build_powerbi.py` first")


def test_pbir_json_valid_against_official_schemas():
    import build_powerbi as B
    assert B.validate_json(PBI / "pbip") == []


def test_csv_tables_reconcile_with_processed_data():
    alerts = pd.read_csv(PBI / "data" / "alerts.csv")
    assert len(alerts) == 1714 and alerts["alert_number"].is_unique
    bridge = pd.read_csv(PBI / "data" / "alert_substances.csv")
    subs = pd.read_csv(PBI / "data" / "substances.csv")
    assert set(bridge["alert_number"]) <= set(alerts["alert_number"])
    assert set(bridge["substance"]) <= set(subs["substance"])
    assert subs["substance"].is_unique  # one side of the relationship must be unique


def test_relationship_columns_exist_in_tmdl():
    d = PBI / "pbip" / "SafetyScope.SemanticModel" / "definition"
    rels = (d / "relationships.tmdl").read_text()
    for table, column in re.findall(r"(?:from|to)Column: (\w+)\.(\w+)", rels):
        tmdl = (d / "tables" / f"{table}.tmdl").read_text()
        assert re.search(rf"^\tcolumn '?{column}'?$", tmdl, re.M), f"{table}.{column} missing"


def test_visuals_reference_existing_fields():
    d = PBI / "pbip" / "SafetyScope.SemanticModel" / "definition" / "tables"
    columns = {t.stem: set(re.findall(r"^\tcolumn '?([^'\n]+)'?$", t.read_text(), re.M)) for t in d.glob("*.tmdl")}
    measures = set(re.findall(r"^\tmeasure '([^']+)'", (d / "Alerts.tmdl").read_text(), re.M))
    for v in (PBI / "pbip").rglob("visual.json"):
        q = json.loads(v.read_text())["visual"]["query"]["queryState"]
        for role in q.values():
            for p in role["projections"]:
                f = p["field"]
                if "Column" in f:
                    ent, prop = f["Column"]["Expression"]["SourceRef"]["Entity"], f["Column"]["Property"]
                    assert prop in columns[ent], f"{v.parent.name}: {ent}.{prop}"
                else:
                    assert f["Measure"]["Property"] in measures, f"{v.parent.name}: {f['Measure']['Property']}"


def test_upload_workbook_has_excel_tables():
    from openpyxl import load_workbook
    wb = load_workbook(PBI / "SafetyScope_PowerBI_upload.xlsx", read_only=False)
    assert {ws.title for ws in wb.worksheets} == {"Alerts", "Substances", "AlertSubstances", "CorrectiveMeasures", "AlertRiskTypes"}
    for ws in wb.worksheets:
        assert ws.title in ws.tables, f"sheet {ws.title} has no Excel Table"
