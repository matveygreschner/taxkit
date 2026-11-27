"""A tiny DSL for writing calculator sheets whose formulas are portable between
Microsoft Excel and Google Sheets.

Portability rules enforced by convention here:
* Only functions both apps share: SUMIFS, SUMPRODUCT, INDEX, MATCH, MIN, MAX,
  IF, AND, OR, ROUND, ROUNDUP, CEILING, ABS. No XLOOKUP/LET/LAMBDA/dynamic arrays,
  no Excel Tables (structured references), no macros, no defined names.
* Every lookup is a bounded range (no whole-column references).

Formulas are written with placeholders that are resolved to cell addresses:

    {key}                    a cell on the current sheet
    {Sheet.key}              a cell on another sheet
    {YEAR}                   the tax-year selector on the Start sheet
    {METHOD}                 "Simplified" or "Law" selector on the Start sheet
    {P:param}                active-year parameter (Rates sheet)
    {PS:param:statuskey}     status-dependent parameter
    {TAX:xkey:statuskey}     cumulative ordinary tax on the value in xkey
    {TAXC25:x:s} {TAXC28:x:s} same, with rates capped at 25% / 28%
    {CGT:x:s}                cumulative 0/15/20% capital gain schedule
    {MINT:x:s}               cumulative "pick smaller" schedule (simplified method)
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

FONT = "Arial"
YEAR_CELL = "Start!$C$6"
METHOD_CELL = "Start!$C$7"

F_TITLE = Font(name=FONT, size=16, bold=True, color="1F3864")
F_SUB = Font(name=FONT, size=10, italic=True, color="595959")
F_HEAD = Font(name=FONT, size=11, bold=True, color="FFFFFF")
F_LABEL = Font(name=FONT, size=10)
F_INPUT = Font(name=FONT, size=10, color="0000FF")
F_CALC = Font(name=FONT, size=10, color="000000")
F_LINK = Font(name=FONT, size=10, color="008000")
F_TOTAL = Font(name=FONT, size=10, bold=True)
F_NOTE = Font(name=FONT, size=9, italic=True, color="595959")
FILL_HEAD = PatternFill("solid", fgColor="1F3864")
FILL_INPUT = PatternFill("solid", fgColor="FFF2CC")
FILL_TOTAL = PatternFill("solid", fgColor="E2EFDA")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

FMT = {
    "money": '$#,##0.00;($#,##0.00);"-"',
    "money0": '$#,##0;($#,##0);"-"',
    "pct": "0.00%",
    "int": "0",
    "num": "#,##0.00",
    "factor": "0.0000",
    "text": "@",
    "year": "0",
}

STATUS_LIST = '"S,MFJ,MFS,HOH,QSS"'
YESNO_LIST = '"Yes,No"'


class Registry:
    """Global map of (sheet, key) -> absolute address, shared by all sheets."""

    def __init__(self):
        self.cells: Dict[str, Dict[str, str]] = {}
        self.rates_rows = 0
        self.ord_rows = (2, 2)
        self.cg_rows = (2, 2)
        self.min_rows = (2, 2)
        self.pending: list = []   # (Calc, cell, formula) resolved after all sheets exist

    def finalize(self):
        for calc, cell, formula in self.pending:
            cell.value = "=" + calc.resolve(formula)
        self.pending.clear()

    def addr(self, sheet: str, key: str) -> str:
        try:
            return self.cells[sheet][key]
        except KeyError:
            raise KeyError(f"Unknown cell {sheet}.{key}") from None


def q(sheet: str) -> str:
    return f"'{sheet}'" if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", sheet) else sheet


class Calc:
    """Builds one calculator sheet top-to-bottom in columns B (label), C (value), D (note)."""

    def __init__(self, wb, reg: Registry, name: str, title: str, subtitle: str = "", widths=(2, 50, 18, 72)):
        self.ws = wb.create_sheet(name)
        self.reg = reg
        self.name = name
        self.reg.cells.setdefault(name, {})
        self.row = 1
        self._dv: Dict[str, DataValidation] = {}
        for i, w in enumerate(widths, start=1):
            self.ws.column_dimensions[get_column_letter(i)].width = w
        self.ws.sheet_view.showGridLines = False
        self.ws["B1"] = title
        self.ws["B1"].font = F_TITLE
        if subtitle:
            self.ws["B2"] = subtitle
            self.ws["B2"].font = F_SUB
        self.row = 4
        self.ws.freeze_panes = "A4"

    # ------------------------------------------------------------ layout --
    def section(self, text: str, cols: str = "BCD"):
        r = self.row
        for c in cols:
            self.ws[f"{c}{r}"].fill = FILL_HEAD
        self.ws[f"{cols[0]}{r}"] = text
        self.ws[f"{cols[0]}{r}"].font = F_HEAD
        self.row += 1

    def note(self, text: str):
        self.ws[f"B{self.row}"] = text
        self.ws[f"B{self.row}"].font = F_NOTE
        self.ws[f"B{self.row}"].alignment = Alignment(wrap_text=False)
        self.row += 1

    def gap(self, n: int = 1):
        self.row += n

    def _register(self, key: str, col: str = "C", row: Optional[int] = None) -> str:
        r = self.row if row is None else row
        a = f"${col}${r}"
        if key in self.reg.cells[self.name]:
            raise ValueError(f"Duplicate key {self.name}.{key}")
        self.reg.cells[self.name][key] = a
        return a

    def _validation(self, cell: str, kind: str):
        if kind not in self._dv:
            formula = {"status": STATUS_LIST, "yesno": YESNO_LIST}.get(kind, kind)
            dv = DataValidation(type="list", formula1=formula, allow_blank=False)
            self.ws.add_data_validation(dv)
            self._dv[kind] = dv
        self._dv[kind].add(cell)

    # ------------------------------------------------------------- cells --
    def inp(self, key: str, label: str, value, fmt: str = "money", note: str = "", choices: str | None = None):
        self._register(key)
        r = self.row
        self.ws[f"B{r}"] = label
        self.ws[f"B{r}"].font = F_LABEL
        c = self.ws[f"C{r}"]
        c.value = value
        c.font = F_INPUT
        c.fill = FILL_INPUT
        c.border = BOX
        c.number_format = FMT.get(fmt, fmt)
        if choices:
            self._validation(f"C{r}", choices)
        if note:
            self.ws[f"D{r}"] = note
            self.ws[f"D{r}"].font = F_NOTE
        self.row += 1

    def calc(self, key: str, label: str, formula: str, fmt: str = "money", note: str = "", total: bool = False):
        self._register(key)
        r = self.row
        self.ws[f"B{r}"] = label
        self.ws[f"B{r}"].font = F_TOTAL if total else F_LABEL
        c = self.ws[f"C{r}"]
        self.reg.pending.append((self, c, formula))
        c.font = F_TOTAL if total else (F_LINK if self._is_pure_link(formula) else F_CALC)
        c.number_format = FMT.get(fmt, fmt)
        c.border = BOX
        if total:
            c.fill = FILL_TOTAL
            self.ws[f"B{r}"].fill = FILL_TOTAL
        if note:
            self.ws[f"D{r}"] = note
            self.ws[f"D{r}"].font = F_NOTE
        self.row += 1

    @staticmethod
    def _is_pure_link(formula: str) -> bool:
        return bool(re.fullmatch(r"\{[A-Za-z0-9_]+\.[A-Za-z0-9_]+\}", formula.strip()))

    # -------------------------------------------------------- resolution --
    def ref(self, token: str) -> str:
        if "." in token:
            sheet, key = token.split(".", 1)
            return f"{q(sheet)}!{self.reg.addr(sheet, key)}"
        return self.reg.addr(self.name, token)

    def resolve(self, formula: str) -> str:
        reg = self.reg

        def rates(col):
            return f"Rates!${col}$2:${col}${reg.rates_rows + 1}"

        def sched(kind, x, s):
            if kind in ("TAX", "TAXC25", "TAXC28"):
                lo, hi = reg.ord_rows
                diff = {"TAX": "F", "TAXC25": "G", "TAXC28": "H"}[kind]
                y, st, low = "A", "B", "D"
            elif kind == "CGT":
                lo, hi = reg.cg_rows
                y, st, low, diff = "K", "L", "N", "P"
            else:  # MINT
                lo, hi = reg.min_rows
                y, st, low, diff = "S", "T", "U", "W"
            rng = lambda c: f"Brackets!${c}${lo}:${c}${hi}"  # noqa: E731
            return (f"SUMPRODUCT(({rng(y)}={YEAR_CELL})*({rng(st)}={s})*({x}>{rng(low)})"
                    f"*({x}-{rng(low)})*{rng(diff)})")

        def sub(m):
            tok = m.group(1)
            if tok == "YEAR":
                return YEAR_CELL
            if tok == "METHOD":
                return METHOD_CELL
            if tok.startswith("PS:"):
                _, key, s = tok.split(":")
                return f'SUMIFS({rates("F")},{rates("A")},"{key}",{rates("B")},{self.ref(s)})'
            if tok.startswith("P:"):
                key = tok[2:]
                return f'SUMIFS({rates("F")},{rates("A")},"{key}")'
            for kind in ("TAXC25", "TAXC28", "TAX", "CGT", "MINT"):
                if tok.startswith(kind + ":"):
                    _, x, s = tok.split(":")
                    return sched(kind, self.ref(x), self.ref(s))
            return self.ref(tok)

        return re.sub(r"\{([^{}]+)\}", sub, formula)

    # ----------------------------------------------------- grid helpers --
    def put(self, coord: str, value, fmt: str = "money", kind: str = "calc", key: str | None = None):
        """Write a single cell anywhere (for grids). ``kind``: calc | input | label | total."""
        c = self.ws[coord]
        if kind in ("calc", "total") and isinstance(value, str):
            self.reg.pending.append((self, c, value))
        else:
            c.value = value
        c.number_format = FMT.get(fmt, fmt)
        c.font = {"input": F_INPUT, "label": F_LABEL, "total": F_TOTAL}.get(kind, F_CALC)
        if kind == "input":
            c.fill = FILL_INPUT
        if kind == "total":
            c.fill = FILL_TOTAL
        if kind != "label":
            c.border = BOX
        if key:
            col = re.match(r"[A-Z]+", coord).group(0)
            row = int(coord[len(col):])
            self._register(key, col, row)

    def header_row(self, labels: List[str], start_col: int = 2):
        r = self.row
        for i, lab in enumerate(labels):
            cell = self.ws.cell(row=r, column=start_col + i, value=lab)
            cell.font = F_HEAD
            cell.fill = FILL_HEAD
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
        self.row += 1
