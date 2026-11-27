---
name: business-tax-optimizer
description: Finds and quantifies federal tax-saving opportunities for U.S. businesses under current (post-OBBBA, 2025-2026) law, with a tested engine that estimates dollar savings and cites authority. Covers entity choice (sole prop / S corp / C corp), S corp reasonable salary, QBI (Section 199A), 100% bonus depreciation, Section 179, cost segregation, manufacturing-building expensing (168(n)), Section 174A R&E expensing and catch-up, the research credit and payroll offset, Section 163(j) interest limits, cash-method changes, PTET elections, retirement plan credits, childcare and paid-leave credits, QSBS, opportunity zones, WOTC and energy deadlines. Use this whenever someone asks how a company, LLC, startup, practice or client can lower its taxes, wants a tax planning review or year-end checklist, or asks whether a business should become an S corp or C corp. Also use when a CPA or finance team needs a client opportunity memo or a "what are we missing" scan from financials, even if they don't say "optimize".
---

# Business Tax Optimizer

This skill turns a company's facts into a ranked list of federal tax opportunities. Each one comes
with an estimated dollar value, the assumptions behind it, the action steps, and the authority. The math runs on the
**TaxKit** engine. Entity comparisons compute the owner's full Form 1040 under each structure,
with payroll taxes and a complete Section 199A calculation, so the estimates are real
computations rather than rules of thumb.

## Workflow

### 1. Gather the profile
Start from whatever the user has: a P&L, a tax return, a description, or answers to questions.
Map it into the fields in `references/profile-fields.md`. A starting template is in
`assets/profile_template.json`. These facts drive the most value; ask for any that are missing
and material:
- entity type and number of owners; owner salary or guaranteed payments; owner filing status and other income
- 3-year average gross receipts (it unlocks the small-business rules at $31M for 2025 and $32M for 2026)
- profit before owner pay; employees and non-owner wages; state income tax rate
- equipment and building purchases this year (cost, class, acquisition date)
- R&D spending (domestic vs. foreign; any unamortized 2022-2024 balance; qualified research expenses for the last 4 years)
- interest expense and EBITDA if receipts exceed the small-business threshold
- retirement plan in place? Plans to sell the company or reinvest gains?

Don't stall on perfect data. Use reasonable estimates and say they are estimates. Unknown fields
default to zero, and checks that need them simply don't fire.

### 2. Run the scan
```bash
python scripts/optimize.py business_scan '{"profile": {...}, "format": "markdown"}'
python scripts/optimize.py business_scan '{"profile": {...}, "xlsx_path": "opportunities.xlsx"}'   # JSON + Excel
```
Put a large profile in a file and pipe it in:
`python scripts/optimize.py business_scan - < request.json`. Python 3.9+ standard library only;
the Excel output needs `openpyxl`.

### 3. Dig into the big items
The scan is a screen. For the top opportunities, run the focused commands and show the numbers:
- `compare_entities` gives the combined entity and owner tax for each structure;
- `reasonable_comp_sweep` gives S corp tax at different salary levels;
- `qbi_deduction_full` gives the Section 199A deduction with the wage and SSTB limits;
- the depreciation, credit and individual commands are listed in `references/commands.md`.

### 4. Write it up
Lead with a short summary table: opportunity, estimated value, type (permanent / timing / credit),
confidence. Then give a section per material item covering what it is, why it applies, the
estimate and its key assumptions, next steps with deadlines, and risks. Say clearly that values
interact and are not additive. Accelerating deductions, for example, changes the marginal rate
used for everything else. Close by recommending review by the company's CPA before acting,
because elections, state conformity and facts the scan can't see change answers.

For a client-ready memo, the tax-memo-writer skill (if installed) produces Facts / Issue /
Analysis / Conclusion format.

## Judgment the scan can't make

Read `references/opportunities.md` for the rules, dates and citations behind each check. Then
apply judgment:
- **Timing vs. permanent.** Bonus depreciation, cost segregation and the cash method mostly move
  tax between years. Value them as present value and mention recapture on sale. Credits and the
  QBI deduction are permanent.
- **Deadlines that have passed.** As of late 2026, the small-business Section 174A retroactive
  election closed July 6, 2026. New Section 179D and 45L projects and wind/solar start-of-construction
  windows closed mid-2026. WOTC lapsed for hires after 2025 unless renewed. Don't present these as available.
- **State conformity.** Many states decouple from bonus depreciation and Section 174A. Flag it.
- **Reasonable compensation.** S corp savings come from paying less than all profit as salary.
  The salary still has to be defensible for the owner's role. Never recommend a salary just
  because it minimizes tax.
- **Exit plans flip the entity answer.** A C corp's double tax can be worth it if QSBS could
  exclude up to $15M of gain on a sale. Ask about the exit before recommending a structure.

## Scope and tone

This is planning analysis, not tax advice or return preparation. It covers federal income and
payroll tax for U.S. businesses. International (FDDEI/NCTI/BEAT), CAMT, state-specific rules and
consolidated returns are summarized in the reference file but not modeled. When a question turns
on them, say so and recommend a specialist. Be direct about uncertainty: if a number depends on
an assumption the user hasn't confirmed, label it.
