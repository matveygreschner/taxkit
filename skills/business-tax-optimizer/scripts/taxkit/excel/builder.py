"""Build the TaxKit workbook (.xlsx) - portable to Microsoft Excel and Google Sheets."""
from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.workbook.properties import CalcProperties

from .core import Registry
from .reference import build_brackets, build_macrs, build_rates, build_start

SHEET_INDEX = [
    ("Tax_Calc", "IRC 1", "Tax from the rate schedule, capital gain worksheet (0/15/20, 25%, 28%), "
                             "bracket table, simplified 'pick smaller' method."),
]


def _calculators():
    from . import sheets_tax
    builders = [sheets_tax.build_tax_calc]
    try:
        from . import sheets_more
        builders += sheets_more.BUILDERS
        SHEET_INDEX.extend(x for x in sheets_more.INDEX if x not in SHEET_INDEX)
    except ImportError:
        pass
    return builders


def build_workbook(path: str | Path, map_path: str | Path | None = None) -> Registry:
    wb = Workbook()
    reg = Registry()
    builders = _calculators()
    start = build_start(wb, SHEET_INDEX + [
        ("Rates", "All", "Every dollar limit and rate for 2025 and 2026 with sources."),
        ("Brackets", "IRC 1", "Ordinary and capital-gain rate schedules by year and status."),
        ("MACRS_Tables", "IRC 168", "IRS Pub. 946 MACRS percentage tables."),
    ])
    build_rates(wb, reg)
    build_brackets(wb, reg)
    build_macrs(wb, reg)
    # Calculators are created after reference data so ranges are known, then moved in front.
    for b in builders:
        b(wb, reg)
    reg.finalize()
    ref_names = ["Rates", "Brackets", "MACRS_Tables"]
    order = [start] + [ws for ws in wb.worksheets if ws.title not in ref_names + ["Start"]] + [
        wb[n] for n in ref_names]
    wb._sheets = order
    wb.calculation = CalcProperties(fullCalcOnLoad=True)
    for ws in wb.worksheets:
        ws.sheet_properties.tabColor = "1F3864" if ws.title in ref_names else (
            "C00000" if ws.title == "Start" else "70AD47")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    if map_path:
        Path(map_path).write_text(json.dumps({s: k for s, k in reg.cells.items()}, indent=1))
    return reg


if __name__ == "__main__":  # pragma: no cover
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "workbook/TaxKit.xlsx"
    build_workbook(out, Path(out).with_suffix(".cells.json"))
    print("wrote", out)
