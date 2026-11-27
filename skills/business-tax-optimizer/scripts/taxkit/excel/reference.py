"""Reference sheets: Start (year selector + index), Rates, Brackets, MACRS_Tables."""
from __future__ import annotations

from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.datavalidation import DataValidation

from .. import params as P
from ..depreciation import CLASSES, CONVENTIONS, macrs_table
from ..rates import min_schedule
from .core import (BOX, F_HEAD, F_INPUT, F_LABEL, F_NOTE, F_SUB, F_TITLE, FILL_HEAD, FILL_INPUT, FMT, Registry)


def _header(ws, row, labels, start=1):
    for i, lab in enumerate(labels):
        c = ws.cell(row=row, column=start + i, value=lab)
        c.font, c.fill = F_HEAD, FILL_HEAD
        c.alignment = Alignment(horizontal="center")


def build_start(wb, sheet_index):
    ws = wb.active
    ws.title = "Start"
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCDE", (2, 34, 16, 90, 4)):
        ws.column_dimensions[col].width = w
    ws["B1"] = "TaxKit - Federal Income Tax Workbook"
    ws["B1"].font = F_TITLE
    ws["B2"] = ("Formula-driven calculators for U.S. individual & business income tax, tax years 2025-2026 "
                "(OBBBA). Works in Microsoft Excel and Google Sheets.")
    ws["B2"].font = F_SUB
    ws["B4"] = "SETTINGS"
    ws["B4"].font = F_HEAD
    for c in "BCD":
        ws[f"{c}4"].fill = FILL_HEAD
    ws["B6"] = "Tax year (drives every sheet)"
    ws["B6"].font = F_LABEL
    ws["C6"] = P.DEFAULT_YEAR
    ws["C6"].font, ws["C6"].fill, ws["C6"].border = F_INPUT, FILL_INPUT, BOX
    ws["C6"].number_format = "0"
    dv = DataValidation(type="list", formula1='"' + ",".join(str(y) for y in P.YEARS) + '"')
    ws.add_data_validation(dv)
    dv.add("C6")
    ws["D6"] = "Choose 2025 or 2026."
    ws["D6"].font = F_NOTE
    ws["B7"] = "Method"
    ws["B7"].font = F_LABEL
    ws["C7"] = "Simplified" if P.WORKBOOK_DEFAULT_METHOD == "simplified" else "Law"
    ws["C7"].font, ws["C7"].fill, ws["C7"].border = F_INPUT, FILL_INPUT, BOX
    dv2 = DataValidation(type="list", formula1='"Law,Simplified"')
    ws.add_data_validation(dv2)
    dv2.add("C7")
    ws["D7"] = ("Law = statutory computation. Simplified = common hand-computation shortcuts. "
                "See the list below.")
    ws["D7"].font = F_NOTE

    r = 8
    for text in ("HOW TO USE",):
        ws[f"B{r}"] = text
        ws[f"B{r}"].font = F_HEAD
        for c in "BCD":
            ws[f"{c}{r}"].fill = FILL_HEAD
    legend = [
        ("Yellow cell, blue text", "Input - type your facts here. Everything else is a formula."),
        ("Black text", "Formula on this sheet. Green text = pulled from another sheet."),
        ("Green-shaded row", "Key answer for that calculator."),
        ("Filing status codes", "S, MFJ, MFS, HOH, QSS (dropdowns on each sheet)."),
        ("Signs", "Enter losses and expenses as positive numbers unless a label says otherwise."),
        ("Rates sheet", "All dollar limits/rates by year with IRC & Rev. Proc. sources. Edit there if needed."),
        ("Google Sheets", "File > Import > Upload this .xlsx, or open it from Drive and 'Save as Google Sheets'."),
    ]
    r += 1
    for a, b in legend:
        ws[f"B{r}"], ws[f"D{r}"] = a, b
        ws[f"B{r}"].font = F_LABEL
        ws[f"D{r}"].font = F_LABEL
        r += 1
    ws["C9"].fill = FILL_INPUT
    ws["C9"].font = F_INPUT
    ws["C9"] = 1000
    ws["C9"].number_format = FMT["money0"]

    r += 1
    ws[f"B{r}"] = "SHEETS"
    ws[f"B{r}"].font = F_HEAD
    for c in "BCD":
        ws[f"{c}{r}"].fill = FILL_HEAD
    r += 1
    for name, authority, desc in sheet_index:
        ws[f"B{r}"] = name
        ws[f"B{r}"].hyperlink = f"#'{name}'!A1"
        ws[f"B{r}"].font = Font(name="Arial", size=10, color="0563C1", underline="single")
        ws[f"C{r}"] = authority
        ws[f"C{r}"].font = F_LABEL
        ws[f"D{r}"] = desc
        ws[f"D{r}"].font = F_LABEL
        r += 1

    for title, rows in (("SIMPLIFIED METHOD vs. LAW (switch with Method above)", P.SIMPLIFIED_METHODS),):
        r += 1
        ws[f"B{r}"] = title
        ws[f"B{r}"].font = F_HEAD
        for c in "BCD":
            ws[f"{c}{r}"].fill = FILL_HEAD
        r += 1
        for where, what in rows:
            ws[f"B{r}"], ws[f"D{r}"] = where, what
            ws[f"B{r}"].font = F_LABEL
            ws[f"D{r}"].font = F_NOTE
            ws[f"D{r}"].alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[r].height = 30
            r += 1
    r += 1
    ws[f"B{r}"] = ("Not tax advice. Verify against the IRC, regulations and current "
                   "IRS guidance before relying on any result.")
    ws[f"B{r}"].font = F_NOTE
    return ws


def build_rates(wb, reg: Registry):
    ws = wb.create_sheet("Rates")
    _header(ws, 1, ["Key", "Status", "Description", 2025, 2026, "Active year", "Source"])
    for col, w in zip("ABCDEFG", (30, 8, 58, 14, 14, 14, 52)):
        ws.column_dimensions[col].width = w
    r = 2
    for key, entry in P.PARAMS.items():
        status_rows = P.STATUSES if P.is_status_param(key) else ("ALL",)
        for st in status_rows:
            ws.cell(r, 1, key).font = F_LABEL
            ws.cell(r, 2, st).font = F_LABEL
            ws.cell(r, 3, entry["desc"]).font = F_LABEL
            for j, y in enumerate(P.YEARS):
                v = P.param(key, y, None if st == "ALL" else st)
                c = ws.cell(r, 4 + j, v)
                c.font = F_INPUT
                c.number_format = FMT["pct"] if isinstance(v, float) and v <= 1 else FMT["money0"]
                if key.startswith("mileage") or key in ("ltc_per_diem",):
                    c.number_format = "$#,##0.000"
            f = ws.cell(r, 6, f"=INDEX(D{r}:E{r},MATCH(Start!$C$6,$D$1:$E$1,0))")
            f.number_format = ws.cell(r, 4).number_format
            ws.cell(r, 7, entry["source"]).font = F_NOTE
            r += 1
    reg.rates_rows = r - 2
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{r - 1}"
    return ws


def build_brackets(wb, reg: Registry):
    ws = wb.create_sheet("Brackets")
    _header(ws, 1, ["Year", "Status", "Idx", "Lower", "Rate", "Diff", "Diff (cap 25%)", "Diff (cap 28%)"], 1)
    _header(ws, 1, ["Year", "Status", "Idx", "Lower", "Rate", "Diff"], 11)
    _header(ws, 1, ["Year", "Status", "Lower", "Min rate", "Diff"], 19)
    for col in "ABCDEFGHKLMNOPSTUVW":
        ws.column_dimensions[col].width = 12
    r = 2
    for y in P.YEARS:
        for s in P.STATUSES:
            for i, (lo, rate) in enumerate(P.ordinary_brackets(y, s), start=1):
                ws.cell(r, 1, y)
                ws.cell(r, 2, s)
                ws.cell(r, 3, i)
                ws.cell(r, 4, lo).number_format = FMT["money0"]
                ws.cell(r, 5, rate).number_format = FMT["pct"]
                prev = "0" if i == 1 else f"E{r - 1}"
                ws.cell(r, 6, f"=E{r}-{prev}").number_format = FMT["pct"]
                p25 = "0" if i == 1 else f"MIN(E{r - 1},0.25)"
                p28 = "0" if i == 1 else f"MIN(E{r - 1},0.28)"
                ws.cell(r, 7, f"=MIN(E{r},0.25)-{p25}").number_format = FMT["pct"]
                ws.cell(r, 8, f"=MIN(E{r},0.28)-{p28}").number_format = FMT["pct"]
                for c in (1, 2, 3, 4, 5):
                    ws.cell(r, c).font = F_INPUT if c in (4, 5) else F_LABEL
                r += 1
    reg.ord_rows = (2, r - 1)
    r = 2
    for y in P.YEARS:
        for s in P.STATUSES:
            for i, (lo, rate) in enumerate(P.capital_gain_brackets(y, s), start=1):
                ws.cell(r, 11, y)
                ws.cell(r, 12, s)
                ws.cell(r, 13, i)
                ws.cell(r, 14, lo).number_format = FMT["money0"]
                ws.cell(r, 15, rate).number_format = FMT["pct"]
                prev = "0" if i == 1 else f"O{r - 1}"
                ws.cell(r, 16, f"=O{r}-{prev}").number_format = FMT["pct"]
                ws.cell(r, 14).font = ws.cell(r, 15).font = F_INPUT
                r += 1
    reg.cg_rows = (2, r - 1)
    r = 2
    for y in P.YEARS:
        for s in P.STATUSES:
            prev = 0.0
            for p, rate in min_schedule(y, s):
                ws.cell(r, 19, y)
                ws.cell(r, 20, s)
                ws.cell(r, 21, p).number_format = FMT["money0"]
                ws.cell(r, 22, rate).number_format = FMT["pct"]
                ws.cell(r, 23, round(rate - prev, 4)).number_format = FMT["pct"]
                prev = rate
                r += 1
    reg.min_rows = (2, r - 1)
    ws.cell(reg.ord_rows[1] + 3, 1, "Ordinary schedule: tax(x) = SUMPRODUCT((x>Lower)*(x-Lower)*Diff). "
                                    "Edit Lower/Rate (blue) only; Diff columns are formulas.").font = F_NOTE
    ws.cell(reg.min_rows[1] + 2, 19, "Simplified 'pick smaller' schedule = min(ordinary, cap-gain) rate at each "
                                     "breakpoint (generated from the two tables).").font = F_NOTE
    ws.freeze_panes = "A2"
    return ws


def build_macrs(wb, reg: Registry):
    ws = wb.create_sheet("MACRS_Tables")
    _header(ws, 1, ["Key", "Convention", "Class"] + [f"Yr {i}" for i in range(1, 22)])
    ws.column_dimensions["A"].width = 10
    r = 2
    for conv in CONVENTIONS:
        for cls in CLASSES:
            ws.cell(r, 1, f"{conv}|{cls}")
            ws.cell(r, 2, conv)
            ws.cell(r, 3, cls)
            pcts = list(macrs_table(cls, conv)) + [0.0] * 21
            for i in range(1, 22):
                ws.cell(r, 3 + i, pcts[i - 1] / 100.0).number_format = "0.000%"
            r += 1
    reg.cells.setdefault("MACRS_Tables", {})["_last"] = str(r - 1)
    ws.cell(r + 1, 1, "Source: IRS Pub. 946 Tables A-1 to A-5 (3/5/7-yr and all half-year); other mid-quarter "
                      "columns generated with the same 200%/150% DB-to-SL method.").font = F_NOTE
    ws.freeze_panes = "D2"
    return ws
