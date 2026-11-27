# Methods, conventions and limits

## Law vs. simplified method

| Topic | `method: "law"` | `method: "simplified"` |
|---|---|---|
| Capital gains / qualified dividends (`income_tax`, `form_1040`) | Schedule D Tax Worksheet: ordinary income first, then 25% / 28% gain, then the adjusted net capital gain at 0/15/20% **by its position in the stack**; final tax = smaller of that or regular tax | Each slice of preferential income is taxed at **min(ordinary rate, capital-gain rate)** at that income level |
| Dividends received deduction (`c_corp_tax`) | 50% / 65% / 100% (IRC 243, post-2017) | 70% / 80% / 100% |
| SEP (`sep_deduction`) | 20% of (net SE income − ½ SE tax) | 20% of net SE income |

The two capital-gain methods differ only when preferential income sits where the ordinary rate is
*below* the capital-gain rate. For example, the 12% band above the 0% threshold. Example: single 2026,
$400K all LTCG → law $52,582.50, simplified $52,554.00.

## Conventions
- Tax uses the **rate schedule**, not the IRS tax table. Under $100K of taxable income the IRS table
  rounds to $50 brackets, so a table result can differ by a few dollars.
- Phase-outs "per $1,000 or fraction" round up (CTC $50; tips/overtime $100; car loan interest $200).
- The IRA phase-out rounds up to the next $10 with a $200 minimum, per the Pub. 590-A worksheet.
- MACRS percentages come from IRS Pub. 946 Tables A-1 to A-5 (half-year, and mid-quarter 3/5/7-year). Other
  mid-quarter classes are generated with the same 200%/150% declining-balance-to-straight-line method.
- Real property uses straight line with the mid-month convention: 27.5 years (330 months) residential,
  39 years (468 months) nonresidential.
- Capital-loss netting keeps carryforwards' character (ST vs. LT) and uses short-term loss first
  against the $3,000 ($1,500 MFS) limit.

## Simplifications (say so when they matter)
- `qbi_deduction` and `form_1040` use the at-or-below-threshold QBI formula. Above the threshold,
  use `qbi_deduction_full` (business optimizer), which applies the W-2 wage / UBIA and SSTB rules,
  or pass `qbi_override` to `form_1040`.
- Charitable limits: each bucket is capped at its % of AGI and the total at 60%; full IRC 170(b) ordering
  is not modeled.
- `kiddie_tax`: one child, ordinary income only, standard deduction.
- Not modeled: AMT, EITC, education credits, premium tax credit, state taxes, passive activity limits,
  at-risk rules, estimated-tax penalties.
- The 2026 long-term-care per-diem limit ($430) should be confirmed against final guidance.
