"""Stage F - build all Power BI assets from the processed data.

Usage:
    python src/build_powerbi.py

Creates (all under powerbi/):
    data/*.csv                          Power BI-ready star-schema tables
    SafetyScope_PowerBI_upload.xlsx     same tables as Excel Tables (browser upload route)
    power_query/*.pq                    Power Query (M) scripts per table
    dax/measures.dax                    DAX measures
    theme/SafetyScope_theme.json        report theme
    pbip/                               hand-authored Power BI Project (TMDL + PBIR)
                                        (opened and refreshed in Power BI Desktop on Windows, 27 Nov 2026)

All PBIP/PBIR JSON files are validated against Microsoft's published JSON
schemas (vendored in powerbi/tools/schemas, MIT licence). TMDL and DAX cannot
be validated on macOS; they were tested by opening the project in Power BI Desktop on Windows.
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from openpyxl.worksheet.table import Table, TableStyleInfo  # noqa: E402

from safetyscope import config as C  # noqa: E402

PBI = C.POWERBI_DIR
NS = uuid.UUID("6f1c2a9e-5b7d-4c1e-9a43-2f0d8e7b1c55")  # fixed namespace -> stable lineage tags


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


# --------------------------------------------------------------------- data --
def build_tables() -> dict[str, pd.DataFrame]:
    a = pd.read_csv(C.PROCESSED_DIR / "alerts_clean.csv", low_memory=False,
                    parse_dates=["weekly_report_date", "publication_date", "first_measure_date"])
    s = pd.read_csv(C.PROCESSED_DIR / "alert_substances.csv")
    m = pd.read_csv(C.PROCESSED_DIR / "alert_measures.csv", parse_dates=["entry_into_force_date"])
    r = pd.read_csv(C.PROCESSED_DIR / "alert_risk_types.csv")

    alerts = pd.DataFrame({
        "alert_number": a["alert_number"], "case_url": a["case_url"], "alert_level": a["alert_level"],
        "user_type": a["user_type"], "notifying_country": a["notifying_country"],
        "origin_country": a["origin_country"],
        "origin_region": a["origin_is_eu"].astype(str).map({"True": "EU member state", "False": "Non-EU"}).fillna("Unknown"),
        "product_type": a["product_type"], "product_group": a["product_group"], "product_name": a["product_name"],
        "brand": a["brand"], "risk_type": a["risk_type"], "primary_substance": a["primary_substance"].fillna("(none extracted)"),
        "weekly_report": a["weekly_report"], "weekly_report_date": a["weekly_report_date"].dt.date,
        "publication_date": a["publication_date"].dt.date, "first_measure_date": a["first_measure_date"].dt.date,
        "days_measure_to_report": (a["weekly_report_date"] - a["first_measure_date"]).dt.days.astype("Int64"),
        "based_on_ingredient_list": a["based_on_ingredient_list"], "has_measured_value": a["has_measured_value"],
        "counterfeit": a["counterfeit"], "alert_number_year": a["alert_number_year"],
    })
    substances = (s[["substance", "abbreviation", "agent_type", "substance_group", "cas_number"]]
                  .drop_duplicates("substance").sort_values("substance").reset_index(drop=True))
    substances["substance_label"] = [f"{ab} ({n})" if isinstance(ab, str) and ab != n else n
                                     for n, ab in zip(substances["substance"], substances["abbreviation"])]
    alert_substances = s[["alert_number", "substance", "mention_order", "confidence"]]
    measures = m[["alert_number", "measure_kind", "measure_group", "measure_category", "economic_operator"]].copy()
    measures["entry_into_force_date"] = m["entry_into_force_date"].dt.date
    risk_types = r[["alert_number", "risk_type"]]
    return {"alerts": alerts, "substances": substances, "alert_substances": alert_substances,
            "corrective_measures": measures, "alert_risk_types": risk_types}


# Column metadata: (csv column, Power BI table, M type, TMDL dataType, summarizeBy)
TYPES = {
    "int": ("Int64.Type", "int64"), "text": ("type text", "string"), "date": ("type date", "dateTime"),
    "bool": ("type logical", "boolean"),
}
TABLE_NAMES = {"alerts": "Alerts", "substances": "Substances", "alert_substances": "AlertSubstances",
               "corrective_measures": "CorrectiveMeasures", "alert_risk_types": "AlertRiskTypes"}


def col_type(df: pd.DataFrame, col: str) -> str:
    if col.endswith("_date"):
        return "date"
    if col in ("days_measure_to_report", "alert_number_year", "mention_order"):
        return "int"
    if df[col].dtype == bool:
        return "bool"
    return "text"


def m_script(file: str, df: pd.DataFrame) -> str:
    types = ", ".join(f'{{"{c}", {TYPES[col_type(df, c)][0]}}}' for c in df.columns)
    return (
        "let\n"
        f'    Source = Csv.Document(File.Contents(DataFolder & "{file}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n'
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),\n"
        f'    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")\n'
        "in\n"
        "    Typed"
    )


CALENDAR_M = (
    "let\n"
    "    StartDate = #date(2020, 1, 1),\n"
    "    EndDate = #date(2026, 12, 31),\n"
    "    Dates = List.Dates(StartDate, Duration.Days(EndDate - StartDate) + 1, #duration(1, 0, 0, 0)),\n"
    '    AsTable = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),\n'
    '    Typed = Table.TransformColumnTypes(AsTable, {{"Date", type date}}),\n'
    '    AddYear = Table.AddColumn(Typed, "Year", each Date.Year([Date]), Int64.Type),\n'
    '    AddMonthNo = Table.AddColumn(AddYear, "Month Number", each Date.Month([Date]), Int64.Type),\n'
    '    AddMonth = Table.AddColumn(AddMonthNo, "Month", each Date.ToText([Date], "yyyy-MM"), type text),\n'
    '    AddQuarter = Table.AddColumn(AddMonth, "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date])) & " " & Text.From(Date.Year([Date])), type text)\n'
    "in\n"
    "    AddQuarter"
)

# ------------------------------------------------------------------ measures --
BMHCA = "Butylphenyl methylpropional"
MEASURES = [
    # (name, DAX, format string, description)
    ("Total Alerts", "DISTINCTCOUNT(Alerts[alert_number])", "#,0",
     "Number of distinct Safety Gate alerts in the current filter context."),
    ("Share of Selected Alerts", "DIVIDE([Total Alerts], CALCULATE([Total Alerts], ALLSELECTED()))", "0.0%",
     "Alerts as a share of all alerts in the current slicer selection."),
    ("BMHCA Alerts", f'CALCULATE([Total Alerts], AlertSubstances[substance] = "{BMHCA}")', "#,0",
     "Alerts whose risk text names BMHCA (butylphenyl methylpropional)."),
    ("BMHCA Share", "DIVIDE([BMHCA Alerts], [Total Alerts])", "0.0%", "Share of alerts naming BMHCA."),
    ("Distinct Chemicals", 'CALCULATE(DISTINCTCOUNT(AlertSubstances[substance]), Substances[agent_type] = "chemical")',
     "#,0", "Number of distinct chemical substances named."),
    ("Substance Mentions", "COUNTROWS(AlertSubstances)", "#,0",
     "Alert-substance pairs. Larger than Total Alerts when alerts name several substances."),
    ("Notifying Countries", "DISTINCTCOUNT(Alerts[notifying_country])", "#,0", "Distinct notifying countries."),
    ("Ingredient-List Based %", "DIVIDE(CALCULATE([Total Alerts], Alerts[based_on_ingredient_list] = TRUE()), [Total Alerts])",
     "0.0%", "Share of alerts whose risk text says the finding is based on the list of ingredients."),
    ("Lab Measurement %", "DIVIDE(CALCULATE([Total Alerts], Alerts[has_measured_value] = TRUE()), [Total Alerts])",
     "0.0%", "Share of alerts reporting a measured value."),
    ("Origin Unknown %", 'DIVIDE(CALCULATE([Total Alerts], Alerts[origin_country] = "Unknown"), [Total Alerts])',
     "0.0%", "Share of alerts with unknown country of origin."),
    ("Median Days Measure to Report", "MEDIAN(Alerts[days_measure_to_report])", "#,0",
     "Median days from the first measure's entry into force to the weekly report."),
    ("Alerts with Ban on Marketing",
     'CALCULATE([Total Alerts], CorrectiveMeasures[measure_group] = "Ban on marketing", CROSSFILTER(CorrectiveMeasures[alert_number], Alerts[alert_number], Both))',
     "#,0", "Alerts with at least one ban-on-marketing measure."),
    ("Alerts with Recall",
     'CALCULATE([Total Alerts], CorrectiveMeasures[measure_group] = "Recall from end users", CROSSFILTER(CorrectiveMeasures[alert_number], Alerts[alert_number], Both))',
     "#,0", "Alerts with at least one recall from end users."),
    ("Recall %", "DIVIDE([Alerts with Recall], [Total Alerts])", "0.0%", "Share of alerts with a recall."),
    ("Alerts with Voluntary Measure",
     'CALCULATE([Total Alerts], CorrectiveMeasures[measure_kind] = "voluntary", CROSSFILTER(CorrectiveMeasures[alert_number], Alerts[alert_number], Both))',
     "#,0", "Alerts with at least one company-initiated (voluntary) measure."),
    ("Measure Rows", "COUNTROWS(CorrectiveMeasures)", "#,0",
     "Number of measures (not alerts). Use Total Alerts for alert counts."),
    ("Alerts per Weekly Report", "AVERAGEX(VALUES(Alerts[weekly_report]), [Total Alerts])", "#,0.0",
     "Average alerts per weekly report in the selection."),
]


def measures_dax() -> str:
    lines = ["// SafetyScope DAX measures (home table: Alerts)",
             "// Executed and validated in Power BI Desktop (Windows, 27 Nov 2026) - see docs/POWER_BI_GUIDE.md", ""]
    for name, expr, fmt, desc in MEASURES:
        lines += [f"// {desc}", f"// Format: {fmt}", f"[{name}] = {expr}", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------- TMDL --
def tmdl_table(name: str, df: pd.DataFrame, source_m: str, measures: list | None = None) -> str:
    t = "\t"
    out = [f"table {name}", f"{t}lineageTag: {tag('table', name)}", ""]
    for mname, expr, fmt, desc in measures or []:
        out += [f"{t}/// {desc}", f"{t}measure '{mname}' = {expr}", f"{t}{t}formatString: {fmt}",
                f"{t}{t}lineageTag: {tag('measure', mname)}", ""]
    for col in df.columns:
        kind = col_type(df, col)
        out += [f"{t}column {col}", f"{t}{t}dataType: {TYPES[kind][1]}"]
        if kind == "date":
            out.append(f"{t}{t}formatString: yyyy-mm-dd")
        if kind == "int":
            out.append(f"{t}{t}formatString: 0")
        out += [f"{t}{t}lineageTag: {tag('column', name, col)}", f"{t}{t}summarizeBy: none",
                f"{t}{t}sourceColumn: {col}", ""]
        if col == "case_url":
            out.insert(-1, f"{t}{t}dataCategory: WebUrl")
    out += [f"{t}partition {name} = m", f"{t}{t}mode: import", f"{t}{t}source ="]
    out += [f"{t}{t}{t}{t}{line}" for line in source_m.splitlines()]
    return "\n".join(out) + "\n"


def calendar_tmdl() -> str:
    t = "\t"
    cols = [("Date", "dateTime", "yyyy-mm-dd"), ("Year", "int64", "0"), ("Month Number", "int64", "0"),
            ("Month", "string", None), ("Quarter", "string", None)]
    out = ["table Calendar", f"{t}lineageTag: {tag('table', 'Calendar')}", f"{t}dataCategory: Time", ""]
    for c, dt, fmt in cols:
        q = f"'{c}'" if " " in c else c
        out += [f"{t}column {q}", f"{t}{t}dataType: {dt}"]
        if c == "Date":
            out.append(f"{t}{t}isKey")
        if fmt:
            out.append(f"{t}{t}formatString: {fmt}")
        out += [f"{t}{t}lineageTag: {tag('column', 'Calendar', c)}", f"{t}{t}summarizeBy: none", f"{t}{t}sourceColumn: {c}", ""]
    out += [f"{t}partition Calendar = m", f"{t}{t}mode: import", f"{t}{t}source ="]
    out += [f"{t}{t}{t}{t}{line}" for line in CALENDAR_M.splitlines()]
    return "\n".join(out) + "\n"


RELATIONSHIPS = [
    # (from = many side, to = one side, cross-filtering)
    ("AlertSubstances", "alert_number", "Alerts", "alert_number", "bothDirections"),
    ("AlertSubstances", "substance", "Substances", "substance", "oneDirection"),
    ("CorrectiveMeasures", "alert_number", "Alerts", "alert_number", "oneDirection"),
    ("AlertRiskTypes", "alert_number", "Alerts", "alert_number", "bothDirections"),
    ("Alerts", "weekly_report_date", "Calendar", "Date", "oneDirection"),
]


def write_semantic_model(root: Path, tables: dict[str, pd.DataFrame]) -> None:
    sm = root / "SafetyScope.SemanticModel"
    d = sm / "definition"
    (d / "tables").mkdir(parents=True, exist_ok=True)
    (sm / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2))
    (d / "database.tmdl").write_text("database SafetyScope\n\tcompatibilityLevel: 1600\n")
    names = [TABLE_NAMES[k] for k in tables] + ["Calendar"]
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", ""]
    model += [f"ref table {n}" for n in names]
    (d / "model.tmdl").write_text("\n".join(model) + "\n")
    (d / "expressions.tmdl").write_text(
        "/// Folder that contains the SafetyScope CSV files (must end with a backslash on Windows).\n"
        'expression DataFolder = "C:\\SafetyScope\\powerbi\\data\\" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
        f"\tlineageTag: {tag('expression', 'DataFolder')}\n")
    for key, df in tables.items():
        name = TABLE_NAMES[key]
        (d / "tables" / f"{name}.tmdl").write_text(
            tmdl_table(name, df, m_script(key, df), MEASURES if name == "Alerts" else None))
    (d / "tables" / "Calendar.tmdl").write_text(calendar_tmdl())
    rels = []
    for f_t, f_c, t_t, t_c, cf in RELATIONSHIPS:
        rels += [f"relationship {tag('rel', f_t, f_c, t_t, t_c)}"]
        if cf == "bothDirections":
            rels.append("\tcrossFilteringBehavior: bothDirections")
        rels += [f"\tfromColumn: {f_t}.{f_c}", f"\ttoColumn: {t_t}.{'Date' if t_c == 'Date' else t_c}", ""]
    (d / "relationships.tmdl").write_text("\n".join(rels))


# --------------------------------------------------------------------- PBIR --
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
VC_SCHEMA = SCHEMA + "visualContainer/2.13.0/schema.json"


def col(table: str, column: str) -> dict:
    return {"field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}},
            "queryRef": f"{table}.{column}", "nativeQueryRef": column}


def meas(name: str) -> dict:
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Alerts"}}, "Property": name}},
            "queryRef": f"Alerts.{name}", "nativeQueryRef": name}


def visual(name: str, vtype: str, x: int, y: int, w: int, h: int, roles: dict, z: int = 0) -> dict:
    return {
        "$schema": VC_SCHEMA, "name": name,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": {"visualType": vtype,
                   "query": {"queryState": {role: {"projections": projs} for role, projs in roles.items()}},
                   "drillFilterOtherVisuals": True},
    }


def card(name, measure, x, y, z):
    return visual(name, "card", x, y, 240, 110, {"Values": [meas(measure)]}, z)


def slicer(name, table, column, x, y, z, w=240, h=150):
    return visual(name, "slicer", x, y, w, h, {"Values": [col(table, column)]}, z)


def bar(name, table, column, measure, x, y, w, h, z):
    return visual(name, "clusteredBarChart", x, y, w, h, {"Category": [col(table, column)], "Y": [meas(measure)]}, z)


PAGES = [
    ("executive_overview", "Executive Overview", [
        card("kpi_alerts", "Total Alerts", 20, 20, 1), card("kpi_bmhca", "BMHCA Share", 280, 20, 2),
        card("kpi_chemicals", "Distinct Chemicals", 540, 20, 3), card("kpi_countries", "Notifying Countries", 800, 20, 4),
        card("kpi_lag", "Median Days Measure to Report", 1040, 20, 5),
        bar("bar_product_group", "Alerts", "product_group", "Total Alerts", 20, 150, 600, 300, 6),
        visual("line_weekly", "lineChart", 640, 150, 620, 300,
               {"Category": [col("Calendar", "Month")], "Y": [meas("Total Alerts")]}, 7),
        slicer("slicer_country", "Alerts", "notifying_country", 20, 470, 8, 300, 230),
        bar("bar_top_substance", "Substances", "substance_label", "Total Alerts", 340, 470, 920, 230, 9),
    ]),
    ("chemical_risk", "Chemical Risk Intelligence", [
        card("kpi_mentions", "Substance Mentions", 20, 20, 1), card("kpi_ingredient", "Ingredient-List Based %", 280, 20, 2),
        card("kpi_lab", "Lab Measurement %", 540, 20, 3),
        slicer("slicer_substance_group", "Substances", "substance_group", 800, 20, 4, 460, 110),
        bar("bar_substances", "Substances", "substance_label", "Total Alerts", 20, 150, 600, 550, 5),
        visual("matrix_substance_product", "pivotTable", 640, 150, 620, 550,
               {"Rows": [col("Substances", "substance_label")], "Columns": [col("Alerts", "product_group")],
                "Values": [meas("Total Alerts")]}, 6),
    ]),
    ("country_market", "Country and Market Analysis", [
        card("kpi_alerts_c", "Total Alerts", 20, 20, 1), card("kpi_unknown", "Origin Unknown %", 280, 20, 2),
        card("kpi_per_report", "Alerts per Weekly Report", 540, 20, 3),
        slicer("slicer_product_group", "Alerts", "product_group", 800, 20, 4, 460, 110),
        bar("bar_notifier", "Alerts", "notifying_country", "Total Alerts", 20, 150, 400, 550, 5),
        bar("bar_origin", "Alerts", "origin_country", "Total Alerts", 440, 150, 400, 550, 6),
        visual("table_profiles", "tableEx", 860, 150, 400, 550,
               {"Values": [col("Alerts", "notifying_country"), meas("Total Alerts"), meas("BMHCA Share"),
                           meas("Ingredient-List Based %"), meas("Lab Measurement %")]}, 7),
    ]),
    ("product_measures", "Product and Corrective Measure Analysis", [
        card("kpi_ban", "Alerts with Ban on Marketing", 20, 20, 1), card("kpi_recall", "Recall %", 280, 20, 2),
        card("kpi_voluntary", "Alerts with Voluntary Measure", 540, 20, 3),
        slicer("slicer_country_p", "Alerts", "notifying_country", 800, 20, 4, 460, 110),
        bar("bar_product_type", "Alerts", "product_type", "Total Alerts", 20, 150, 600, 550, 5),
        bar("bar_measure_group", "CorrectiveMeasures", "measure_group", "Measure Rows", 640, 150, 620, 260, 6),
        visual("table_alerts", "tableEx", 640, 430, 620, 270,
               {"Values": [col("Alerts", "alert_number"), col("Alerts", "product_type"), col("Alerts", "brand"),
                           col("Alerts", "primary_substance"), col("Alerts", "case_url")]}, 7),
    ]),
]


def write_report(root: Path) -> None:
    rep = root / "SafetyScope.Report"
    d = rep / "definition"
    if d.exists():
        shutil.rmtree(d)
    (d / "pages").mkdir(parents=True)
    (rep / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../SafetyScope.SemanticModel"}}}, indent=2))
    (d / "version.json").write_text(json.dumps({"$schema": SCHEMA + "versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2))
    (d / "report.json").write_text(json.dumps({"$schema": SCHEMA + "report/3.3.0/schema.json", "themeCollection": {}}, indent=2))
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": SCHEMA + "pagesMetadata/1.1.0/schema.json", "pageOrder": [p[0] for p in PAGES],
        "activePageName": PAGES[0][0]}, indent=2))
    for name, display, visuals in PAGES:
        pd_ = d / "pages" / name
        (pd_ / "visuals").mkdir(parents=True)
        (pd_ / "page.json").write_text(json.dumps({
            "$schema": SCHEMA + "page/2.1.0/schema.json", "name": name, "displayName": display,
            "displayOption": "FitToPage", "height": 720, "width": 1280}, indent=2))
        for v in visuals:
            (pd_ / "visuals" / v["name"]).mkdir()
            (pd_ / "visuals" / v["name"] / "visual.json").write_text(json.dumps(v, indent=2))
    (root / "SafetyScope.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": "SafetyScope.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2))
    (root / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")


def validate_json(root: Path) -> list[str]:
    """Validate every PBIP/PBIR JSON file against the vendored Microsoft schemas."""
    from jsonschema import Draft7Validator
    from referencing import Registry, Resource

    sdir = PBI / "tools" / "schemas"
    registry = Registry()
    for f in sdir.glob("*.json"):
        doc = json.loads(f.read_text())
        res = Resource.from_contents(doc, default_specification=__import__("referencing").jsonschema.DRAFT7)
        registry = registry.with_resource(doc["$id"], res)
        if doc["$id"].endswith("schema.embedded.json"):  # referenced as schema-embedded.json
            registry = registry.with_resource(doc["$id"].replace("schema.embedded.json", "schema-embedded.json"), res)
    errors, checked = [], 0
    for f in sorted(root.rglob("*")):
        if f.suffix not in (".json", ".pbir", ".pbism", ".pbip"):
            continue
        doc = json.loads(f.read_text())
        sid = doc.get("$schema")
        if not sid:
            continue
        schema = registry.contents(sid)
        validator = Draft7Validator(schema, registry=registry)
        for err in validator.iter_errors(doc):
            errors.append(f"{f.relative_to(root)}: {err.message[:200]} at {list(err.path)}")
        checked += 1
    print(f"Schema validation: {checked} files checked, {len(errors)} errors")
    return errors


def theme() -> dict:
    return {
        "name": "SafetyScope",
        "dataColors": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
        "background": "#FFFFFF", "foreground": "#1F1F1D", "tableAccent": "#2A78D6",
        "good": "#0CA30C", "neutral": "#EDA100", "bad": "#E34948",
        "textClasses": {
            "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": "#1F1F1D"},
            "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": "#1F1F1D"},
            "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": "#1F1F1D"},
            "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": "#52514E"},
        },
        "visualStyles": {"*": {"*": {
            "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}}],
            "border": [{"show": True, "color": {"solid": {"color": "#E6E5E1"}}, "radius": 4}],
            "dropShadow": [{"show": False}],
        }}},
    }


def write_upload_workbook(tables: dict[str, pd.DataFrame]) -> Path:
    path = PBI / "SafetyScope_PowerBI_upload.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for key, df in tables.items():
            df.to_excel(xw, sheet_name=TABLE_NAMES[key], index=False)
    wb = load_workbook(path)
    for ws in wb.worksheets:
        ref = f"A1:{ws.cell(row=ws.max_row, column=ws.max_column).coordinate}"
        t = Table(displayName=ws.title, ref=ref)
        t.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
        ws.add_table(t)
        ws.freeze_panes = "A2"
    wb.save(path)
    return path


def main() -> None:
    tables = build_tables()
    (PBI / "data").mkdir(parents=True, exist_ok=True)
    for key, df in tables.items():
        df.to_csv(PBI / "data" / f"{key}.csv", index=False)
    write_upload_workbook(tables)

    (PBI / "power_query").mkdir(exist_ok=True)
    (PBI / "power_query" / "DataFolder_parameter.pq").write_text(
        '"C:\\SafetyScope\\powerbi\\data\\" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n')
    for key, df in tables.items():
        (PBI / "power_query" / f"{TABLE_NAMES[key]}.pq").write_text(m_script(key, df) + "\n")
    (PBI / "power_query" / "Calendar.pq").write_text(CALENDAR_M + "\n")
    (PBI / "dax").mkdir(exist_ok=True)
    (PBI / "dax" / "measures.dax").write_text(measures_dax())
    (PBI / "theme").mkdir(exist_ok=True)
    (PBI / "theme" / "SafetyScope_theme.json").write_text(json.dumps(theme(), indent=2))

    root = PBI / "pbip"
    root.mkdir(exist_ok=True)
    write_semantic_model(root, tables)
    write_report(root)
    errors = validate_json(root)
    for e in errors:
        print("  ", e)
    print({k: len(v) for k, v in tables.items()})
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
