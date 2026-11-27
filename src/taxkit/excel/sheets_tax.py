"""Tax_Calc sheet: rate schedule, capital-gain worksheet, bracket table."""
from __future__ import annotations

from .core import Calc


def build_tax_calc(wb, reg):
    c = Calc(wb, reg, "Tax_Calc", "Tax Calculator - Rate Schedule & Capital Gains",
             "IRC 1(a)-(d), 1(h). Ordinary brackets + Schedule D Tax Worksheet.")
    c.section("INPUTS")
    c.inp("status", "Filing status", "S", "text", "S / MFJ / MFS / HOH / QSS", choices="status")
    c.inp("ti", "Taxable income (Form 1040 line 15)", 400_000)
    c.inp("qd", "Qualified dividends", 0)
    c.inp("ltcg", "Net capital gain eligible for preferential rates", 400_000,
          note="Smaller of net LTCG or net capital gain (Sch. D line 15/16). Includes 25%/28% gain below.")
    c.inp("u1250", "  of which: unrecaptured Sec. 1250 gain (max 25%)", 0)
    c.inp("coll", "  of which: collectibles / 28% rate gain", 0, note="Art, antiques, stamps, gems")
    c.gap()

    c.section("STATUTORY COMPUTATION (Schedule D Tax Worksheet)")
    c.calc("ti0", "Taxable income (floored at 0)", "MAX(0,{ti})")
    c.calc("pref", "Total preferential income", "MIN({ti0},MAX(0,{qd})+MAX(0,{ltcg}))")
    c.calc("u1250x", "Unrecaptured 1250 gain used", "MIN(MAX(0,{u1250}),MAX(0,{ltcg}),{pref})")
    c.calc("collx", "28% gain used", "MIN(MAX(0,{coll}),MAX(0,{ltcg})-{u1250x},{pref}-{u1250x})")
    c.calc("ancg", "Adjusted net capital gain (0/15/20%)", "{pref}-{u1250x}-{collx}")
    c.calc("below25", "Income taxed below 25% (top of 24% bracket)",
           "SUMIFS(Brackets!$D$%d:$D$%d,Brackets!$A$%d:$A$%d,{YEAR},Brackets!$B$%d:$B$%d,{status},"
           "Brackets!$C$%d:$C$%d,5)" % ((reg.ord_rows[0], reg.ord_rows[1]) * 4), "money0")
    c.calc("ord", "Amount (A): taxed at ordinary rates", "MAX({ti0}-{pref},MIN({below25},{ti0}-{ancg}))",
           note="IRC 1(h)(1)(A): 25%/28% gain sitting in brackets below 25% is taxed at ordinary rates")
    c.calc("stack_c", "Top of ANCG layer", "{ord}+{ancg}")
    c.calc("flat", "25%/28% gain taxed at flat rates", "MAX(0,{ti0}-{ord}-{ancg})")
    c.calc("at25", "  at 25% (unrecaptured 1250)", "MIN({u1250x},{flat})")
    c.calc("at28", "  at 28% (collectibles)", "{flat}-{at25}")
    c.calc("t_ord", "Tax on amount (A)", "{TAX:ord:status}")
    c.calc("t_ancg", "Tax on ANCG (0/15/20%, directly above A)", "{CGT:stack_c:status}-{CGT:ord:status}")
    c.calc("t_1250", "Tax on unrecaptured 1250 gain (25%)", "0.25*{at25}")
    c.calc("t_coll", "Tax on 28% gain", "0.28*{at28}")
    c.calc("regular", "Regular tax if all income were ordinary", "{TAX:ti0:status}")
    c.calc("tax_law", "Tax - LAW (Schedule D worksheet)",
           "ROUND(MIN({regular},{t_ord}+{t_1250}+{t_coll}+{t_ancg}),2)")
    c.calc("t_ancg_c", "Tax on ANCG - simplified 'pick smaller' per band", "{MINT:stack_c:status}-{MINT:ord:status}",
           note="Each slice taxed at min(ordinary rate, capital-gain rate)")
    c.calc("tax_simplified", "Tax - SIMPLIFIED method", "ROUND(MIN({regular},{t_ord}+{t_1250}+{t_coll}+{t_ancg_c}),2)")
    c.calc("tax", "INCOME TAX (method selected on Start)",
           "IF({METHOD}=\"Law\",{tax_law},{tax_simplified})", total=True)
    c.calc("tax_diff", "Simplified minus law", "{tax_simplified}-{tax_law}",
           note="Non-zero only when gains sit in a band where the ordinary rate is below the cap-gain rate.")
    lo, hi = reg.ord_rows
    rng = lambda col: f"Brackets!${col}${lo}:${col}${hi}"  # noqa: E731
    c.calc("marg", "Marginal ordinary rate",
           f"SUMPRODUCT(({rng('A')}={{YEAR}})*({rng('B')}={{status}})"
           f"*(MAX(0.01,{{ti0}})>{rng('D')})*{rng('F')})", "pct")
    c.calc("eff", "Effective (average) rate", "IF({ti0}>0,{tax}/{ti0},0)", "pct")
    c.gap()

    c.section("ANCG BY RATE BAND")
    c.calc("cg_top0", "Top of 0% band", "SUMIFS(Brackets!$N$%d:$N$%d,Brackets!$K$%d:$K$%d,{YEAR},"
           "Brackets!$L$%d:$L$%d,{status},Brackets!$M$%d:$M$%d,2)" % ((reg.cg_rows[0], reg.cg_rows[1]) * 4))
    c.calc("cg_top15", "Top of 15% band", "SUMIFS(Brackets!$N$%d:$N$%d,Brackets!$K$%d:$K$%d,{YEAR},"
           "Brackets!$L$%d:$L$%d,{status},Brackets!$M$%d:$M$%d,3)" % ((reg.cg_rows[0], reg.cg_rows[1]) * 4))
    c.calc("at0", "ANCG taxed at 0%", "MAX(0,MIN({stack_c},{cg_top0})-{ord})")
    c.calc("at15", "ANCG taxed at 15%", "MAX(0,MIN({stack_c},{cg_top15})-MAX({ord},{cg_top0}))")
    c.calc("at20", "ANCG taxed at 20%", "MAX(0,{ancg}-{at0}-{at15})")
    c.gap()

    c.section("BRACKET-BY-BRACKET TABLE (ordinary income only)")
    c.header_row(["Bracket", "Lower bound", "Rate", "Amount in bracket", "Tax"], 2)
    lo, hi = reg.ord_rows
    first = c.row
    for i in range(1, 8):
        r = c.row
        c.put(f"B{r}", i, "int", "label")
        c.put(f"C{r}", "SUMIFS(Brackets!$D$%d:$D$%d,Brackets!$A$%d:$A$%d,{YEAR},Brackets!$B$%d:$B$%d,{status},"
                       "Brackets!$C$%d:$C$%d,%d)" % (lo, hi, lo, hi, lo, hi, lo, hi, i), "money0")
        c.put(f"D{r}", "SUMIFS(Brackets!$E$%d:$E$%d,Brackets!$A$%d:$A$%d,{YEAR},Brackets!$B$%d:$B$%d,{status},"
                       "Brackets!$C$%d:$C$%d,%d)" % (lo, hi, lo, hi, lo, hi, lo, hi, i), "pct")
        upper = f"C{r + 1}" if i < 7 else "{ti0}"
        c.put(f"E{r}", f"MAX(0,MIN({{ti0}},{upper})-C{r})", "money")
        c.put(f"F{r}", f"E{r}*D{r}", "money")
        c.row += 1
    c.put(f"E{c.row}", f"SUM(E{first}:E{c.row - 1})", "money", "total")
    c.put(f"F{c.row}", f"SUM(F{first}:F{c.row - 1})", "money", "total", key="table_tax")
    c.ws.column_dimensions["E"].width = 18
    c.ws.column_dimensions["F"].width = 16
    c.row += 1
    return c
