"""Build the workbook and recalculate it with an independent formula engine,
comparing against the Python engine (a small fuzz run; CI uses more)."""
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest

from taxkit.excel.builder import build_workbook

ROOT = Path(__file__).resolve().parents[1]
BANNED = ("XLOOKUP", "XMATCH", "LET(", "LAMBDA(", "FILTER(", "SORT(", "UNIQUE(", "SEQUENCE(", "_xlfn", "[@", "INDIRECT(")


@pytest.fixture(scope="module")
def workbook(tmp_path_factory):
    out = tmp_path_factory.mktemp("wb") / "TaxKit.xlsx"
    build_workbook(out, out.with_suffix(".cells.json"))
    return out


def test_formulas_are_portable(workbook):
    """Only functions that behave identically in Excel and Google Sheets."""
    wb = openpyxl.load_workbook(workbook)
    found = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    assert "{" not in c.value, f"unresolved placeholder in {ws.title}!{c.coordinate}"
                    found += [(ws.title, c.coordinate, b) for b in BANNED if b in c.value.upper()]
    assert not found


def test_workbook_matches_engine(workbook):
    pytest.importorskip("formulas")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_workbook.py"), str(workbook), "--fuzz", "3"],
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
