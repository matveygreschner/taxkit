"""Compare values computed by another spreadsheet app against the reference engine.

Use it to prove the workbook computes identically in Google Sheets (or Excel, LibreOffice...):
open workbook/TaxKit.xlsx in the app, let it recalculate, export/save as .xlsx, then

    python scripts/compare_export.py path/to/exported.xlsx [workbook/TaxKit.xlsx]

Every formula cell of the original is compared with the exported cached value.
"""
from __future__ import annotations

import sys

import formulas
import openpyxl


def main(exported: str, original: str = "workbook/TaxKit.xlsx") -> int:
    other = openpyxl.load_workbook(exported, data_only=True)
    ours = openpyxl.load_workbook(original)
    sol = formulas.ExcelModel().loads(original).finish().calculate()
    ref = {}
    for k, v in sol.items():
        if "!" in k and "]" in k:
            sheet = k.rsplit("!", 1)[0].split("]", 1)[1].rstrip("'").upper()
            ref[(sheet, k.rsplit("!", 1)[1])] = v.value
    n = diffs = errors = 0
    for ws in ours.worksheets:
        ows = other[ws.title]
        for row in ws.iter_rows():
            for c in row:
                if not (isinstance(c.value, str) and c.value.startswith("=")):
                    continue
                n += 1
                got = ows[c.coordinate].value
                if isinstance(got, str) and got.startswith("#"):
                    errors += 1
                    print("ERROR", ws.title, c.coordinate, got)
                    continue
                exp = ref.get((ws.title.upper(), c.coordinate))
                exp = exp[0, 0] if hasattr(exp, "shape") else exp
                try:
                    same = abs(float(got or 0) - float(exp or 0)) < 0.005
                except (TypeError, ValueError):
                    same = str(got) == str(exp)
                if not same:
                    diffs += 1
                    if diffs <= 20:
                        print("DIFF", ws.title, c.coordinate, "app=", got, "reference=", exp)
    dv = sum(len(list(ws.data_validations.dataValidation)) for ws in other.worksheets)
    dv0 = sum(len(list(ws.data_validations.dataValidation)) for ws in ours.worksheets)
    print(f"{n} formula cells: {diffs} differences, {errors} errors; dropdown rules {dv}/{dv0}")
    return 1 if diffs or errors or dv < dv0 else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
