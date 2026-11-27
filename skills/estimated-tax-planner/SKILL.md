---
name: estimated-tax-planner
description: Exact U.S. estimated tax planning for 2025-2026. It covers the IRC 6654 safe harbors (90% current-year, 100% or 110% prior-year), the Form 2210 underpayment penalty computed installment by installment at the real quarterly IRS interest rates, 1040-ES voucher amounts, and a year-end projection that ranks the fixes. Those fixes are extra W-4 withholding, a January 15 payment, and an IRA distribution with withholding (rolled over or kept), each ranked by net benefit after its own cost. Use this whenever someone asks how much to pay in estimated taxes or quarterly taxes, whether they will owe an underpayment penalty, what Form 2210 says, how to avoid a penalty before year-end, or what to put on their 1040-ES vouchers. Also use it for a freelancer, contractor or business owner with irregular income, or when a W-2 earner has a big gain or bonus. It runs the full Form 1040 engine instead of a flat-rate estimate.
---

# Estimated Tax Planner

Quarterly-estimate questions look simple, and most answers to them are wrong. A flat "22% of
profit" estimate misses several things:
- self-employment tax;
- the safe-harbor rule that sets the real target;
- the fact that withholding counts as paid evenly through the year while a voucher counts only from the day it's paid;
- the per-installment penalty math.

This skill does all of that with **TaxKit**'s tested engine. The tax comes from a full Form 1040.
The penalty is a Form 2210 ledger: each payment is applied to the oldest shortfall first, and interest
is split at each quarterly IRS rate change.

## How to run it

```bash
python scripts/estimate.py list                                    # every command and its arguments
python scripts/estimate.py describe year_end_projection
python scripts/estimate.py year_end_projection - < request.json   # large inputs from a file
```
Python 3.9+, standard library only. Dates are `YYYY-MM-DD`, money is dollars, rates are decimals.

## Workflow

1. **Collect the facts.**
   - The projected full-year return: the same fields as `form_1040`. `withholding` is the expected total for the year, including remaining paychecks.
   - Estimated payments made or scheduled, with dates.
   - Last year's **total tax** and **AGI** (Form 1040 lines 24 and 11), and last year's filing status.
   - Whether the person has wages, their age, and an IRA, if the IRA remedy might matter.

   If last year's figures are missing, ask. They often set a lower target than 90% of this year.
2. **Run `year_end_projection`.** It returns:
   - the projected tax and the safe harbor that applies, or an exemption;
   - what is still needed under each harbor;
   - the penalty if nothing changes;
   - the remedies ranked by net benefit, with ties going to the simplest fix (W-4 withholding first).
3. **Present it plainly.** Use a short table with the target, paid so far, still needed, and the penalty if nothing changes. Then give the remedies in rank order with amounts and deadlines. Point out why extra withholding beats a January payment: it counts as paid evenly through the year, so it fixes earlier quarters too.
4. **For planning next year**, use `safe_harbor` with this year's figures as `prior_year`, then `estimate_vouchers`.

## Interest rates

A penalty runs until **April 15 of the following year**. So a **2025** penalty needs rates only
through April 15, 2026, and they're all bundled. A **2026** penalty needs the 2027 Q1 and Q2 IRC 6621
rates. The bundled table covers 2025 Q1 through 2026 Q4; for any quarter it lacks, the engine **refuses
to guess**:
- If you can browse, fetch the current rate from `https://www.irs.gov/payments/quarterly-interest-rates` and pass it as `rate_overrides` (for example `{"2027Q1": 0.07}`).
- Otherwise pass `rate_assumption: "hold_last"` and tell the user the penalty is a projection at the last announced rate. The output marks it `projected: true`.

Never present a projected penalty as final.

## Example request

```json
{"return_inputs": {"year": 2025, "status": "MFJ", "wages": 120000, "schedule_c_profit": 80000,
                   "qualifying_children": 1, "withholding": 12000},
 "estimated_payments": [{"date": "2025-04-15", "amount": 3000}, {"date": "2025-06-16", "amount": 3000},
                        {"date": "2025-09-15", "amount": 3000}],
 "as_of": "2025-11-26",
 "prior_year": {"tax": 24000, "agi": 160000, "status": "MFJ"},
 "taxpayer_age": 40,
 "ira": {"balance": 500000, "rollover_dates_last_12_months": [], "cash_available_for_60_days": 10000}}
```

Field notes:
- **Status codes:** `S`, `MFJ`, `MFS`, `HOH`, `QSS`.
- **Payments:** list only payments made or definitely scheduled. In late November the January 15 payment hasn't happened yet; leave it out, and the projection shows it as a remedy.
- **Joint returns with self-employment income:** `se_person_wages` is the self-employed spouse's own W-2 wages. On a joint return it defaults to 0, meaning the other spouse has the W-2.
- **IRA withholding:** if `withholding_rate` is omitted, the remedy is shown both at the 10% default and with 100% elected on Form W-4R. With 100% elected, the distribution is smallest.

## What the commands cover

- `safe_harbor`:
  - the §6654(e)(1) under-$1,000 exception and the §6654(e)(2) zero-prior-year exception;
  - 90% / 100% / 110%, using prior-year AGI over $150K, or $75K for MFS;
  - combining or allocating last year's tax when the couple filed jointly one year and separately the other;
  - short prior years;
  - farmers and fishermen at 66⅔% with one Jan 15 installment;
  - the §6654(h) January 31 rule.
- `underpayment_penalty`: the regular-method ledger, with:
  - the IRC 7503 weekend and holiday shifts (including DC Emancipation Day);
  - §7508A disaster postponements;
  - actual withholding dates, if elected.
- `year_end_projection`, with IRA remedies sized at the **10% default withholding** on IRA distributions (§3405(b)), or the rate elected on Form W-4R.
  - **Rollover version:** it checks the 60-day cash requirement and the one-rollover-per-12-months rule (§408(d)(3)(B)).
  - **Kept version:** it costs the extra income tax plus the §72(t) 10% if the owner is under 59½, and it is usually ranked "not recommended".
- `estimate_vouchers` and `installment_due_dates`.

See `references/rules.md` for the authorities and conventions.

## Limits

Say so when a question depends on one of these:
- The annualized installment method (Schedule AI) isn't built yet. When income is lumpy, say it might lower the penalty and that the regular method shown is an upper bound.
- State estimated taxes aren't covered.
- Corporate estimates (Form 2220) aren't covered.
- Penalty waivers for casualty or reasonable cause (§6654(e)(3)) are the IRS's decision, so the tool doesn't model them.

This is planning help, not tax advice.
