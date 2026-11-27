---
name: us-tax-calculator
description: Exact U.S. federal income tax calculations for tax years 2025 and 2026 (post-OBBBA) using a tested engine instead of mental math. Use this whenever someone asks to compute or check a tax number. Covers tax on taxable income or capital gains, a full Form 1040, standard vs. itemized deductions, the SALT cap, self-employment or payroll tax, child tax credit, kiddie tax, the senior/tips/overtime deductions, capital gain netting, basis and gain on a sale, home-sale exclusion, partnership or S corp basis, C corp tax and DRD, MACRS / Section 179 / bonus depreciation, imputed interest, annuities, Social Security taxation, casualty losses, NOLs, vacation homes, and IRA or SEP limits. Trigger even when the user just pastes a tax problem or practice question, asks "how much tax would I owe", or wants a tax spreadsheet. It can also generate a formula-driven Excel / Google Sheets workbook.
---

# U.S. Tax Calculator

This skill wraps **TaxKit**, a tested Python engine for federal income tax. It is checked against 70+ worked
textbook examples and 1,400+ cross-checks against its own spreadsheet. Every rate and limit
for 2025 and 2026 comes with its IRC / Rev. Proc. source.

Why use it rather than computing in your head: tax math chains many small rules: bracket
stacking, phase-outs rounded per $1,000, wage-base caps, and the capital gain worksheet. Each is easy to get slightly
wrong. The engine gets them right and shows its work, so you can explain the answer instead of
guessing it.

## How to run it

Everything goes through one script that takes JSON and prints JSON. It needs Python 3.9+ and
only the standard library; `openpyxl` is needed just for the workbook command.

```bash
python scripts/tax.py list                                  # all commands with their arguments
python scripts/tax.py describe form_1040                    # arguments + explanation for one command
python scripts/tax.py income_tax '{"taxable_income": 400000, "status": "S", "net_ltcg": 400000}'
python scripts/tax.py form_1040 '{"status": "MFJ", "wages": 150000, "qualifying_children": 2,
                                  "itemized": {"state_local_taxes": 18000, "mortgage_interest": 14000}}'
```

A complete example with investment income. Note the fields that repeat on purpose:
qualified dividends are part of ordinary dividends; net LTCG goes in both the Schedule D net and the
preferential-rate amount; and NIIT needs `net_investment_income` explicitly.

```bash
python scripts/tax.py form_1040 '{"year": 2026, "status": "MFJ", "wages": 185000,
  "ordinary_dividends": 4000, "qualified_dividends": 4000,
  "net_capital_gain": 30000, "net_ltcg_for_rates": 30000,
  "net_investment_income": 34000, "qualifying_children": 2, "withholding": 19500}'
# -> agi 219,000; taxable_income 186,800; income_tax 28,140; total_tax 23,740; balance_due 4,240
```

Run commands from this skill's directory (use `python3` if `python` isn't on the path), or pass the full path to `scripts/tax.py`. Filing
statuses are `S`, `MFJ`, `MFS`, `HOH` and `QSS`. `year` defaults to 2026. Amounts are dollars;
percentages are decimals (`0.30` for 30%). Enter losses and expenses as positive numbers unless
an argument name says otherwise.

## Workflow

1. **Pin down the facts**: year, filing status, and each amount. If something material is missing,
   such as filing status or which year, ask. Otherwise state a reasonable assumption and continue.
2. **Pick the command.** Use `references/commands.md` to map the question to a command. Run
   `describe <command>` if you're unsure of an argument name. Common ones:
   - bracket tax → `income_tax` (`bracket_breakdown` for the bracket table)
   - full return → `form_1040`
   - gains → `net_capital_gains`, `sale`, `amount_realized`, `adjusted_basis`
   - depreciation → `personal_property_schedule`, `real_property_depreciation`, `sec179_allowed`
   - entities → `owner_reporting` (entity codes `sole_prop`, `partnership`, `s_corp`, `c_corp`),
     `c_corp_tax`; **whether a partnership / S corp distribution or loss is taxable or allowed →
     `basis_rollforward`** (contributions, income, distributions, then losses, with suspended losses)
3. **Run it and read the whole result**, not just the bottom line. Intermediate fields (ordinary
   vs. preferential portion, phase-out amounts, carryforwards) are usually what the user needs to
   see or explain.
4. **Present the answer** with the key steps, the final number, and the rule that drove it. Put
   numbers in a small table when there are several. If you made assumptions, say so.

## Two computation methods

`income_tax`, `form_1040`, `c_corp_tax` and `sep_deduction` accept `"method": "law"` (statute,
the default for the first three) or `"method": "simplified"`. Simplified mode reproduces common
hand-computation shortcuts:
- capital gains taxed band-by-band at the smaller of the ordinary and capital-gain rate;
- the pre-2018 70% / 80% dividends-received deduction;
- SEP = 20% of net SE income.

Use `law` unless the user asks for the simplified method. If the two
differ, show both and explain why. `references/methods.md` has the details and the known
simplifications (for example, AMT and EITC are not modeled).

## Rates and limits

`params` returns every parameter for a year, optionally for one filing status, each with its
source. Use it to quote a figure like the 2026 standard deduction or SALT cap. A readable table
is in `references/rates-2025-2026.md`.

## Spreadsheet output

`python scripts/tax.py workbook '{"out": "TaxKit.xlsx"}'` writes a 16-sheet workbook with live
formulas. It opens in Excel, or in Google Sheets via File > Import. Offer it when the user wants
something they can reuse, such as a client file or a planning model.

## Scope

This is for federal income tax planning and education. It is not filing software and not tax
advice. State tax, AMT, EITC, education credits and the QBI wage/SSTB limits are outside the
individual engine. The business-tax-optimizer skill has a full Section 199A computation. Say so when a question
depends on something not modeled, rather than approximating silently.
