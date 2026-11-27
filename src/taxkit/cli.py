"""Command line: ``python -m taxkit <command>``.

    python -m taxkit build [out.xlsx]               build the workbook
    python -m taxkit tax 400000 --status S          tax on taxable income
    python -m taxkit tax 400000 --status S --ltcg 400000 --year 2025
    python -m taxkit brackets 400000 --status MFJ   bracket-by-bracket table
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .params import DEFAULT_YEAR, STATUSES
from .rates import bracket_breakdown, income_tax


def main(argv=None):
    ap = argparse.ArgumentParser(prog="taxkit", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="generate the Excel / Google Sheets workbook")
    b.add_argument("out", nargs="?", default="workbook/TaxKit.xlsx")
    for name in ("tax", "brackets"):
        p = sub.add_parser(name)
        p.add_argument("taxable_income", type=float)
        p.add_argument("--status", default="S", choices=STATUSES)
        p.add_argument("--year", type=int, default=DEFAULT_YEAR)
        p.add_argument("--qd", type=float, default=0.0, help="qualified dividends")
        p.add_argument("--ltcg", type=float, default=0.0, help="net capital gain for preferential rates")
        p.add_argument("--method", default="law", choices=("simplified", "law"),
                       help="law = Schedule D worksheet (default); simplified = 'pick smaller' shortcut")
    a = ap.parse_args(argv)

    if a.cmd == "build":
        from .excel.builder import build_workbook
        out = Path(a.out)
        build_workbook(out, out.with_suffix(".cells.json"))
        print(f"wrote {out}")
        return
    if a.cmd == "tax":
        r = income_tax(a.taxable_income, a.status, a.year, a.qd, a.ltcg, method=a.method)
        other = income_tax(a.taxable_income, a.status, a.year, a.qd, a.ltcg,
                           method="law" if a.method == "simplified" else "simplified")
        print(f"{a.year} {a.status}  taxable income ${r.taxable_income:,.2f}")
        print(f"  regular tax (all ordinary)   ${r.regular_tax:,.2f}")
        if a.qd or a.ltcg:
            print(f"  ordinary portion             ${r.ordinary_portion:,.2f} -> ${r.tax_on_ordinary:,.2f}")
            print(f"  ANCG at 0% / 15% / 20%       ${r.ancg_at_0:,.0f} / ${r.ancg_at_15:,.0f} / ${r.ancg_at_20:,.0f}")
            other_name = "statute (Sch. D worksheet)" if a.method == "simplified" else "simplified 'pick smaller'"
            print(f"  {other_name:28} ${other.tax:,.2f}")
        print(f"  INCOME TAX ({a.method})        ${r.tax:,.2f}")
        print(f"  marginal {r.marginal_rate:.0%}   effective {r.effective_rate:.2%}")
        return
    rows = bracket_breakdown(a.taxable_income, a.status, a.year)
    print(f"{'Rate':>5} {'From':>12} {'To':>12} {'Amount':>14} {'Tax':>12}")
    for row in rows:
        to = f"{row.upper:,.0f}" if row.upper else "and up"
        print(f"{row.rate:>5.0%} {row.lower:>12,.0f} {to:>12} {row.amount_in_bracket:>14,.2f} {row.tax:>12,.2f}")
    print(f"{'':>45} {sum(r.tax for r in rows):>12,.2f}")


if __name__ == "__main__":  # pragma: no cover
    main()
