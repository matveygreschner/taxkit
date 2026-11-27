# Roadmap: the next three TaxKit skills

> Selected by a 16-agent adversarial tournament (4 rounds of attack, defend and judge), run on 2026-11-26 against a market survey of existing tax skills. The worked examples below were re-run on the engine and match.


## The recommendation

| Rank | Skill | What it does | Effort (one person, ~12 h/week) |
|---|---|---|---|
| **1** | **`estimated-tax-planner`** | §6654 safe harbors, the Form 2210 penalty with quarterly §6621 rates, the annualized method, and a year-end "what to do before Dec 31" projection | ~58 h, about 5 weeks |
| **2** | **`tax-provision-740`** | ASC 740 current and deferred tax, DTA/DTL roll-forward, valuation-allowance mechanics, and the ASU 2023-09 rate reconciliation with the 5% test, including OBBBA effects | ~92 h, about 8 weeks |
| **3** | **`retirement-distribution-planner`** | RMDs (ages 73/75, Uniform Lifetime table), Roth conversion bracket-filling, and IRMAA cliffs, all run through your existing Form 1040 engine | ~49 h, about 4 weeks |

**Build them in that order.** That's about **207 hours** of itemized work (8 hours of shared plumbing plus the three skills), and I add a separate **~31-hour contingency (15%)** on top, so plan on **about 238 hours, or about 20 weeks at 12 hours a week** (late November 2026 to late April 2027). Each estimate is a line-by-line budget in "Build order and effort", and each skill has a **cut line**: a smaller first release that ships on time if the full scope overruns.

Why these three:
- **#1** is the most direct fix for a gap I can show you. Anthropic's only tax-computing skill uses a flat 22% rate. TaxKit can compute the real tax, the real safe harbor and the real penalty with your existing engine. Its first release is also the smallest: about 36 hours to the cut line.
- **#2** is the skill accounting employers will notice most. Provision work is a core job in Big 4 tax and corporate tax departments, and nobody publishes a tested, transparent provision engine. It reuses your C corp, depreciation and OBBBA business parameters, and its law changes arrive as dated federal enactments and standards, not as a stream of mid-year state rule changes.
- **#3** reuses the most of your engine. Each Roth-conversion scenario is a full Form 1040 run, and the OBBBA senior deduction creates hidden marginal rates that only a real engine shows.

Sales-tax nexus came a close fourth. "Why not the others" explains why it lost.

### Assumptions
- **Employers.** "AI accounting and finance roles" mainly means public-accounting tax practices, corporate tax departments and tax-technology teams, plus some wealth-management firms. Tools #1 and #2 aim at the first three groups and #3 at the last two.
- **Effort.** Estimates assume about 12 hours a week and include tests, SKILL.md and packaging.
- **Scope of "gaps".** A gap here means no deterministic, tested Claude skill exists. Commercial software that does the job doesn't close a gap. It does count against a choice when free, authoritative tools already cover the same need, which is part of why nexus ranks fourth.
- **Example numbers.** All worked numbers below come from running your current `taxkit` engine. They are marked where they rely on hypothetical inputs, such as a prior-year tax amount.

---

## How I chose: edge cases first

For each candidate I worked one realistic case from start to finish with your engine. Then I listed the ways the tool could give a confidently wrong answer. A candidate ranked higher when:
- its dangerous edge cases can be closed with deterministic code and tests;
- its authorities publish worked examples you can test against;
- its parameters don't go stale faster than one person can update them.

The examples taught me three design rules. All three skills follow them:

1. **Keep the arithmetic separate from the tax-year data.** The 2210 penalty arithmetic doesn't depend on the year: give it tax, payments and a rate table and it computes the penalty. If you hard-wire 2025–2026 into it, you can't test against IRS examples from earlier years. Every parameter table should carry dates and sources, like `params.py` does now.
2. **Never fill in an unknown value quietly. Refuse it, or take it from the caller with a label.** TaxKit already follows this rule. `live.underpayment_rate` raises "No bundled rate ... pass it as an override" for a quarter it doesn't have, and tags caller-supplied rates `"caller-supplied (live)"`. The new skills keep that design rather than inventing a second one. A 2026 underpayment penalty runs into 2027 at rates that may not be announced yet: the skill fetches them from irs.gov and passes them as overrides, or it stops. A 2026 Roth conversion sets 2028 Medicare premiums, and the 2028 thresholds don't exist yet. The caller must pick a projection method, and every figure built on it is labeled "projected".
3. **Python does the mechanics; the person makes the judgments.** Whether a valuation allowance is needed, or whether an IRMAA surcharge is worth paying, is a judgment. The Python computes the inputs to those decisions exactly and returns them as labeled options.

---

## 1. `estimated-tax-planner` (build first)

### The worked example

**Facts.** A married couple filing jointly for 2025:
- $120,000 of W-2 wages, with $12,000 withheld;
- $80,000 of Schedule C profit;
- one qualifying child;
- four $3,000 estimated payments, each made on its due date;
- hypothetical 2024 figures: AGI $160,000 and total tax $24,000.

**Step 1: compute 2025 tax with your existing engine.** One `form_1040` call gives:
- AGI of $194,348.18;
- income tax of $22,383.28 plus SE tax of $11,303.64, less the $2,200 CTC;
- **total tax of $31,486.92**, with $7,486.92 due at filing.

**Step 2: find the required annual payment.** It is the lesser of two amounts:
- 90% of 2025 tax, which is $28,338.23;
- 110% of 2024 tax, which is $26,400.00. The 110% figure applies because 2024 AGI was over $150,000.

The required payment is **$26,400**, or $6,600 per installment.

**Step 3: build the installment ledger.** Withholding counts as paid in equal parts on the four due dates (§6654(g)). That gives $3,000 + $3,000 = $6,000 per quarter. Each payment first covers the oldest shortfall (§6654(b)), so the shortfalls build up:

| Installment due | Shortfall carried | Days | Rate | Penalty |
|---|---|---|---|---|
| Apr 15, 2025 | $600 | 62 (to Jun 16) | 7% | $7.13 |
| **Jun 16, 2025** (Jun 15 was a Sunday, §7503) | $1,200 | 91 | 7% | $20.94 |
| Sep 15, 2025 | $1,800 | 122 | 7% | $42.12 |
| Jan 15, 2026 | $2,400 | 75 at 7% + 15 at 6% (to Apr 15) | 7% → 6% | $40.44 |
| **Total** | | | | **≈ $110.63** |

**What the example taught me:**
- **Rates can change inside one shortfall.** The last row starts at 7% and ends at 6%, so the ledger has to split the days at the rate-change date: Jan 16 to Mar 31 is 75 days at 7%, and Apr 1 to 15 is 15 days at 6%. The convention the tests must pin down is the one the Form 2210 Part IV worksheet uses. Days are counted from the day after the due date (or after the previous payment) up to and including the date paid, ending no later than April 15. A payment made on the due date accrues 0 days. A late payment made on day N accrues N days, not N+1.
- **Withholding and estimated payments are timed differently.** If they add **$2,400 of extra December withholding**, the penalty drops to **$0**, because withholding counts as paid evenly through the year. If they instead send a $2,400 estimated payment on Jan 15, the penalty is still **$70.19**, because Q1–Q3 stay short. That difference is the year-end advice clients actually need, and the planner should rank both options.
- **A large balance due doesn't mean a large penalty.** They owe $7,487 at filing, but the penalty is based only on a $2,400 shortfall pattern. A flat-22% skill can't produce any of these numbers.

### Edge cases the design must survive

| Edge case | Handling |
|---|---|
| Prior-year AGI exactly $150,000 | The 110% rule needs AGI *over* $150K ($75K MFS), so this is 100%. Test the boundary. |
| No prior-year return, or a short prior year | The prior-year safe harbor is unavailable; return a 90%-only result. |
| Prior year had zero tax, full 12 months, citizen or resident | §6654(e)(2) exception: no penalty. |
| Tax after withholding under $1,000 | §6654(e)(1): no penalty. `safe_harbor` takes `withholding` as an input for exactly this test: $12,000 of tax with $11,500 withheld returns "exempt, §6654(e)(1)" and no installments. |
| Return filed and all tax paid by Jan 31 | §6654(h): the Q4 installment is excused. |
| MFJ this year but separate returns last year, or the reverse | Prior-year tax is combined or allocated as the 2210 instructions require. This needs the prior year's own status and, for a joint-to-separate change, both spouses' prior separate-basis tax, so those are fields of the `prior_year` input. |
| Farmers and fishermen | 66⅔% and a single Jan 15 installment (§6654(i)). |
| Disaster postponement (§7508A), such as the 2025 Los Angeles wildfire relief | Accept a postponement window; no penalty accrues inside it. |
| Due date on a weekend or legal holiday | Adjust by §7503 using a small holiday table: DC Emancipation Day plus the federal holidays. |
| Lumpy income, such as a Q4 bonus or a December asset sale | Annualized method (Schedule AI), computed line by line rather than by rerunning the return on income × 4 (see Scope). Each installment uses the smaller of the annualized and regular amounts, and any saving is recaptured in later installments. |
| A 2026 penalty that runs into 2027 | Rates come from the existing `live.underpayment_rate`. If Q1 or Q2 2027 isn't bundled yet, the engine raises. The SKILL.md tells the model to fetch the rate from irs.gov/payments/quarterly-interest-rates and pass it as an override. The output then lists each quarter's rate source (bundled or caller-supplied). The engine never substitutes the last known rate. |
| A remedy that costs more than the penalty it avoids | Every year-end remedy reports its own cost next to the penalty it avoids (see `year_end_projection`). An IRA distribution under age 59½ that isn't rolled back over costs income tax plus the §72(t) 10%. |
| Overpayment applied from the prior year | Treat it as paid on Apr 15. |
| Actual withholding dates elected instead of the equal split | Accept a list of withholding dates. |

### Scope

Commands registered through `api.register`, the same way `taxkit.business` does it:
- `safe_harbor(current_tax, withholding, status, prior_year=None, citizen_or_resident=True, farmer_fisherman=False, filed_and_paid_by_jan31=False)` returns the required annual payment, the method that set it, the four installments, and any exception that applies.
  - `prior_year` is one dict: `{tax, agi, status, full_12_months, spouse_separate_tax=None}`. Its `status` is last year's status, which can differ from this year's `status`; that difference is what triggers the MFJ/MFS combine-or-allocate rule, and `spouse_separate_tax` supplies the second figure when the allocation needs it (the call raises if it is required and missing). `None` means no prior-year return: only the 90% harbor applies, and the output says why.
  - The checks run in a fixed order: §6654(e)(1) (`current_tax − withholding` under $1,000), then §6654(e)(2) (prior-year tax of zero, a full 12-month year, and `citizen_or_resident`), then the 90% / 100% / 110% computation (66⅔% for farmers and fishermen, with a single Jan 15 installment). `filed_and_paid_by_jan31` excuses the Q4 installment under §6654(h).
- `underpayment_penalty(required_installments, payments[], withholding, withholding_dates=None, rate_table=None, postponements=[])` returns the ledger above, row by row with day counts, plus the total. **It works for any year.**
- `annualized_installments(periods[4], status, year)`. Each period (Jan 1 to Mar 31, May 31, Aug 31 and Dec 31) is a cumulative dict with its own `agi`, `itemized`, `qbi_inputs`, `se_net_profit`, `credits` and `other_taxes`. It follows Schedule AI line by line and does **not** rerun `form_1040` on income × 4:
  - **Part I.** Annualize AGI with factors 4 / 2.4 / 1.5 / 1. Annualize itemized deductions with the same factors and compare them with the **full, unannualized** standard deduction. Compute the QBI deduction on the annualized figures. Tax the annualized taxable income with the existing `rates` functions. Subtract the period's credits and add other taxes. Multiply by the applicable percentages 22.5 / 45 / 67.5 / 90%.
  - **Part II (SE tax).** Compute SE tax separately, period by period. Period net earnings × 0.9235 are measured against a **prorated** Social Security wage base, then multiplied by the form's combined annualize-and-rate factors: 0.496 / 0.2976 / 0.186 / 0.124 on the Social Security portion and 0.116 / 0.0696 / 0.0435 / 0.029 on the Medicare portion. There is no per-period $400 floor. Half of the result flows back into Part I as the deduction. Check the exact prorated base amounts and factors on the 2025 and 2026 Schedule AI before coding.
  - **This needs a small refactor of `payroll.py`, not a parameter override.** The current `payroll.self_employment_tax(se_income, status, year, w2_wages, medicare_wages_on_return)` reads `ss_wage_base` internally, zeroes net earnings under $400, and adds Additional Medicare in the same call. None of that fits Schedule AI. A naive reuse is wrong: $420 of Jan–Mar Schedule C profit is $387.87 of net earnings, which the annual function turns into $0 SE tax. The refactor is:
    - extract `se_components(nese, ss_base_left, year)`, which returns the Social Security and Medicare amounts with no floor and no Additional Medicare;
    - have `self_employment_tax` call it after its own $400 rule and wage-base lookup, so its results and existing tests don't change;
    - have Schedule AI call `se_components` with the prorated base and apply its own factors.

    That is about 2 hours, inside the Schedule AI budget, and the existing `payroll` tests are the regression check.
  - **Withholding** stays spread evenly unless the caller supplies actual dates. It is not "annualized".
- `year_end_projection(ytd_return, remaining_income, payments_so_far, as_of, prior_year, taxpayer_age, has_wages, ira=None)` returns what is still owed for each safe harbor.
  - `prior_year` is the same dict `safe_harbor` takes, and `year_end_projection` passes it through unchanged along with the projected tax and the withholding to date, so the two can't disagree. If it is missing, only the 90% harbor is computed and the output says why.
  - `ira` is `{balance, rollover_dates_last_12_months[], cash_available_for_60_days, withholding_rate=None}`. If it is missing, the two IRA remedies are listed as "not evaluated: no IRA input" rather than guessed.
  - **IRA withholding rate.** An IRA distribution is a nonperiodic distribution, so the default federal withholding is **10%** (§3405(b)), and the owner can elect any rate from 0% to 100% on Form W-4R. The mandatory 20% of §3405(c) applies only to eligible rollover distributions from qualified plans, 403(b)s and governmental 457(b)s, **not to IRAs**. The engine sizes every IRA remedy from `withholding_rate` (10% when it is `None`, and the output says the default was used), and it also shows the elected-100% option, which needs the smallest distribution.

  It then compares remedies on **net benefit = penalty avoided − the remedy's own cost**, never on penalty avoided alone:
  - **Jan 15 estimated payment.** No extra cost; it is tax owed anyway. It doesn't fix the shortfalls in earlier quarters.
  - **Extra December W-4 withholding** (only if `has_wages`). No extra cost, and it counts as paid evenly, so it can cure every quarter.
  - **IRA distribution with withholding, rolled back over within 60 days.** The withheld amount counts as paid evenly (§6654(g)). If the full gross amount is rolled over within 60 days (§408(d)(3)), it adds no income. Only the net amount reaches the owner, so the withheld part must be replaced from other cash; that cash comes back only as a smaller balance due or a refund at filing. To get $2,400 of withholding for the worked couple: at the 10% default that is a $24,000 distribution, rolling over $24,000 with $2,400 of other cash; with 100% elected it is a $2,400 distribution, rolling over $2,400, all of it from other cash. Either way the cash needed is the withholding amount, and the engine requires `ira.cash_available_for_60_days` ≥ that amount. It also checks the one-rollover-per-12-months limit (§408(d)(3)(B)) against `ira.rollover_dates_last_12_months`. The cost is the use of that cash, plus the risk of missing the deadline.
  - **IRA distribution kept, not rolled over.** Its cost is the incremental income tax, computed by rerunning `form_1040` with and without it. Add the §72(t) 10% if `taxpayer_age` is under 59½ and no exception is entered. Take the worked couple, under 59½. With the 10% IRA default, curing a $110.63 penalty this way takes a $24,000 distribution that costs about **$7,680** (22% + 10%; their taxable income of about $148,000 stays inside the 22% bracket, which runs to $206,700, even with the extra $24,000). Even with 100% withholding elected, the $2,400 distribution costs about $770. The tool ranks this remedy last and says why.
  - Remedies with a negative net benefit are listed as "not recommended" with the number, not hidden.
- `estimate_vouchers(year)` returns the 1040-ES amounts and due dates.

**Outputs:** JSON for the model, and an optional sheet built with your Excel DSL that reproduces the Form 2210 Part III/IV worksheet with live formulas.

### How it reuses TaxKit

- **Tax figures.** `form_1040` produces "current-year tax" for the safe-harbor test. That covers SE tax, Additional Medicare, NIIT, CTC/ACTC and the OBBBA deductions. It also gives the with/without cost of a remedy. Schedule AI reuses the lower-level pieces (`rates`, `individual.qbi_deduction`, `individual.standard_deduction`) on the annualized amounts each line calls for, plus the new `payroll.se_components` core described above.
- **Withholding check.** `fica` and `payroll` check that the withholding entered is plausible.
- **§6621 rates: reuse, don't duplicate.** TaxKit already has `live.underpayment_rate`: a dated 2025Q1–2026Q4 table (7/7/7/7, 7/6/7/7) with its IRS source string. It is registered in `api.COMMANDS`, has an override path and is tested in `tests/test_live.py`. The penalty ledger calls it for each quarter a shortfall spans and passes the caller's `overrides` through. There is one source of truth, and the yearly update is still adding rows to that one dict.
- **Data and packaging.** The other year parameters (the $150K/$75K test, the $1,000 threshold, installment dates) go in `params.py`. Packaging uses the existing `build_skills.py` vendoring.

### Test strategy

1. **IRS worked examples.** Use the examples in **Pub. 505**, chapter 4, for the regular and annualized methods, and the **Form 2210 instructions**. Prior-year editions work as fixtures too, because the penalty arithmetic takes the rate table as input.
2. **The example above as a fixture.** Assert $110.63, the 75/15 day split at the Apr 1 rate change, $0 with December withholding and $70.19 with a Jan 15 payment. Add a day-count test: a payment on the due date accrues 0 days, one a day late accrues 1 day, and accrual stops at April 15 even for later payments.
   - **Remedy-ranking test.** For the same couple with `taxpayer_age=40` and the hypothetical 2024 figures as `prior_year`, a kept IRA distribution must show a negative net benefit and rank below both the withholding and the Jan 15 options. With `withholding_rate=None` the IRA remedy must be sized at $24,000 gross (10% default), never $12,000; with `withholding_rate=1.0` it must be $2,400. With `cash_available_for_60_days` of $2,399 the rollover remedy must be rejected for insufficient cash.
   - **`safe_harbor` exception tests.** $12,000 of tax with $11,500 withheld returns the §6654(e)(1) exemption and no installments; $1,000.00 after withholding does not. Zero prior-year tax with `full_12_months=True` and `citizen_or_resident=True` is exempt, and the same with `citizen_or_resident=False` is not. MFJ this year with a prior `status` of MFS combines both spouses' prior tax, and a missing `spouse_separate_tax` raises. A rolled-over distribution must show zero income-tax cost. With a rollover dated within the last 12 months, the rollover remedy must be rejected with the §408(d)(3)(B) reason; with `ira=None`, both IRA remedies must be "not evaluated".
   - **Schedule AI test.** A case that itemizes in period 1 below the standard deduction must use the full standard deduction. A Schedule C earner above the prorated wage base in period 1 must cap Social Security tax at the prorated base. A $420 Jan–Mar profit must produce non-zero period-1 SE tax (no $400 floor per period), while `self_employment_tax` on $420 for the full year still returns $0.
3. **Property tests:**
   - an extra payment never raises the penalty;
   - paying earlier never raises it;
   - the penalty is zero when every cumulative installment is met;
   - the penalty is linear in the shortfall within a single rate period.
4. **Boundary tests.** Test every row of the edge-case table, including AGI of $150,000.00 vs $150,000.01 and tax after withholding of $999.99 vs $1,000.00.
5. **Head-to-head eval** (`evals/`). Show that Anthropic's `tax-prep` flat-22% method on the same facts asks for the wrong quarterly amount. This makes a strong README point.

### Sources and the parameters to verify before coding

- **Statutes:** IRC §6654(a)–(l), §6621(a)(2) (federal short-term rate + 3%), §7503 and §7508A.
- **IRS publications:**
  - Form 2210 and instructions (2025);
  - Form 2210 Schedule AI;
  - Form 1040-ES (2026);
  - Pub. 505 (2026).
- **Parameters to verify:**
  - Quarterly underpayment rates: **7% for 2025, 7% for Q1 2026, 6% for Q2 2026, 7% for Q3–Q4 2026.** These are already in `live.UNDERPAYMENT_RATES`. Re-check them against the IRS quarterly news releases, and add 2027Q1 to that same table when it is announced.
  - The $150,000 / $75,000 AGI test and the $1,000 threshold. Neither is indexed.
  - The annualization periods and factors.
  - Installment dates for 2025 (Apr 15, **Jun 16**, Sep 15, Jan 15, 2026) and 2026 (Apr 15, Jun 15, Sep 15, Jan 15, 2027).
  - The **day-count convention** in the Form 2210 Part IV worksheet (days after the due date up to and including the payment date, capped at April 15), and the 365-day basis. 2028 is a leap year, so a 2027 penalty that runs into 2028 uses 366.
  - The Schedule AI prorated Social Security wage-base amounts for 2025 and 2026, the Part II combined factors, and how the instructions treat the $400 rule in the annualized computation.
  - The §72(t) exceptions list, and the 60-day and one-per-12-months rollover rules (§408(d)(3)), for the remedy costs.
  - IRA withholding: the 10% default on nonperiodic distributions (§3405(b)) and the 0–100% election on Form W-4R, versus the mandatory 20% that applies only to eligible rollover distributions from employer plans (§3405(c)). Check the current Form W-4R instructions.
  - The yearly-moving inputs to Schedule AI and the ledger: the Social Security wage base ($176,100 for 2025, $184,500 for 2026) and the four prorated amounts derived from it, the §7503 holiday table, and any §7508A disaster postponements declared for the year.

### Why it beats the alternatives

- It fixes a gap you can show, in Anthropic's own skill.
- It reuses the most for the least new code.
- Its authority is unusually clean: one Code section, one form, and IRS worked examples.
- Every individual-tax practice files 2210s.
- Maintenance is a bounded yearly refresh, about **4–6 hours**: four §6621 rate rows; the Social Security wage base and the four Schedule AI prorated amounts; the year's installment dates after §7503 weekend and holiday shifts; the 1040-ES voucher figures; and the year's §7508A disaster postponements. The postponements are the only part that arrives during the year. They are inputs (`postponements=[]`), so a new declaration needs no code change, only an optional entry in a dated table. Every item comes from one IRS page or form, and each can be checked by a test that fails when the year has no entry.
- It also gives you the payment-timing ledger the retirement planner reuses (#3).
- It extends a feature you already ship (`underpayment_rate`) instead of adding a parallel one.

---

## 2. `tax-provision-740` (the employer showcase)

### The worked example

**Facts.** A calendar-year 2026 C corporation, federal only:
- pretax book income of **$10,000,000**;
- permanent items: nondeductible meals of $100,000 and fines of $50,000;
- a research credit of $200,000, after the §280C election;
- tax depreciation over book depreciation of $2,000,000, from 100% bonus;
- a $300,000 increase in the warranty reserve;
- $600,000 reversing from the **2022–2024 capitalized domestic R&E**. The company chose the two-year ratable §174A transition, so half was deducted in 2025 and half in 2026.

**Current tax.** Taxable income is 10,000,000 + 150,000 − 2,000,000 + 300,000 − 600,000 = **$7,850,000**. At 21% that is $1,648,500, less the $200,000 credit, so **current tax is $1,448,500**. Your `c_corp_tax` already produces the pre-credit figure, including the DRD, the 1% charitable floor and the 80% NOL limit.

**Deferred tax:**
- the DTL increases by 2,000,000 × 21% = $420,000 (expense);
- the warranty DTA increases by $63,000 (benefit);
- the §174 DTA reverses by $126,000 (expense);

so **deferred tax expense is $483,000**.

**Total provision: $1,931,500, an ETR of 19.315%.**

**ASU 2023-09 rate reconciliation.** The 5% threshold is 5% × (pretax income × 21%) = **$105,000**.

| Line | Amount | Rate |
|---|---|---|
| Statutory tax at 21% | $2,100,000 | 21.000% |
| Tax credits: research credit (≥ $105K, so it gets its own line) | (200,000) | (2.000)% |
| Nontaxable or nondeductible items (meals $21,000 and fines $10,500, each under $105K, so aggregated) | 31,500 | 0.315% |
| **Total** | **$1,931,500** | **19.315%** |

Cross-check: (10,000,000 + 150,000) × 21% − 200,000 = $1,931,500. The provision equals current + deferred and equals the rate reconciliation total, to the cent. That three-way identity is the backbone of the test suite.

**What the example taught me:**
- **The §174A transition is an election, so it's an input.** If the company had deducted the whole 2022–24 balance in 2025, the 2026 reversal is zero. Small businesses with $31M or less in receipts could instead amend 2022–24, but that window closed on July 6, 2026, as your optimizer already notes.
- **Foreign R&E still amortizes over 15 years.** It stays a growing DTA and must not be swept into the domestic unwind.
- **The 5% test depends on the size of pretax income.** It needs special handling when pretax income is negative or near zero.
- **The 5% test splits items, it doesn't drop categories.** The nondeductible line stays even though both items in it are under the threshold; only their separate display depends on 5%.

### Edge cases the design must survive

| Edge case | Handling |
|---|---|
| Pretax book **loss** | Take the 5% threshold on the absolute value. When pretax is near zero, report the ETR as "not meaningful" instead of dividing. |
| **Sign conventions** (DTA +, DTL −), the classic provision error | One convention set in code, plus a test that each temporary difference's sign is applied correctly in both directions. |
| Post-2017 NOLs: no expiry, 80% limit | Schedule DTA reversals. An indefinite-lived DTL (a "naked credit", such as tax-amortized goodwill) supports an indefinite NOL DTA only **up to 80%**. The Python computes that limited source of income; the valuation allowance decision stays the user's judgment, and the output says so. |
| Valuation allowance | An input, with a mechanical "sources of income" schedule: reversing DTLs, carrybacks where allowed, and projected income entered by the user. Python never decides it. |
| Items recorded in OCI (AFS securities, pensions) | A separate column in the roll-forward, so they never reach the income-statement provision. |
| State tax | A single blended state rate in v1, deductible federally, so the reconciliation line is "state, net of federal effect". Separate states are a v2 item. |
| Enactment-date effects | Under ASC 740-10-35-4 a law change is recognized in the period that **contains the enactment date**. The tool stores each law with its enactment date (OBBBA: July 4, 2025) and compares it with the provision period's own `period_start` and `period_end`, never with a year label. A calendar-2026 provision gets its OBBBA effects through opening balances, so an OBBBA "enacted in the current period" line is rejected. A fiscal year from July 1, 2025 to June 30, 2026 contains July 4, 2025, so the same line is **required** there, in the ASU 2023-09 category "effect of changes in tax laws or rates enacted in the current period". Tests cover both cases plus a fiscal year ending July 3, 2025 (rejected). |
| Mixed bonus vintages | The rate depends on the acquisition date **and** the placed-in-service year. Property acquired after Jan 19, 2025 gets 100%. Property acquired before Jan 20, 2025 (including under a binding contract) gets **40% if placed in service in 2025 and 20% if placed in service in 2026**, so the calendar-2026 worked example would use 20% for any such asset. Reuse `bonus_pre_jan20_2025` from `bparams`, which already stores {2025: 0.40, 2026: 0.20}, keyed by placed-in-service year. (Its `desc` string says "placed in service 2025" only; fix that text while you are there.) Tests assert both vintages. |
| NCTI / FDDEI (tax years beginning after Dec 31, 2025) | v1 takes them as input lines placed in the "cross-border tax laws" category. v1.1 computes the §250 deductions. CAMT and BEAT are explicitly out of scope, and the skill says so. |
| Uncertain tax positions | A roll-forward of the input UTB amounts, with an "unrecognized tax benefits" reconciliation line. The two-step recognition judgment is left to the model and the memo skill. |
| Rounding | Compute in cents. The reconciliation must foot exactly with **no plug**; an unexplained difference fails loudly. |

### Scope

Commands:
- `provision(pretax_income, permanent[], temporary[], credits[], state_rate, prior_balances, elections, period_start, period_end)` returns current tax, deferred tax, the total, and the ETR. The period dates drive the enactment-date check and support fiscal-year filers.
- `deferred_rollforward(...)` returns beginning DTA/DTL, P&L, OCI, other movements and ending balances, by temporary difference.
- `rate_reconciliation(..., entity_type="PBE")` returns the ASU 2023-09 table. Each prescribed category with a nonzero amount is a required line; the 5% test decides only which items inside a category, and which "other" items, get their own lines. Non-PBEs get the qualitative version.
- `va_sources_of_income(...)` returns the reversal schedule and the 80%-limited capacity.
- `schedule_m3_map(...)` maps book-tax differences to Form 1120 Schedule M-3 line groups. **This is v1.1**, after the first release, so it is not in the v1 budget.
- `provision_workbook(...)` builds a formula-driven provision workbook with the Excel DSL. This is the deliverable reviewers actually open.

### How it reuses TaxKit

- **Current tax.** `entities.c_corp_tax` supplies taxable income and the 21% tax, with DRD, charity limits and the NOL.
- **Depreciation.** `depreciation.personal_property_schedule` produces the tax side. Add a small straight-line book helper to produce the book side and the temporary difference.
- **OBBBA parameters.** `business/bparams` and `opportunities.py` already encode §174A dates, bonus vintages, §163(j) EBITDA and the §280C 79% election. The provision uses those parameters directly, so the optimizer and the provision can never disagree.
- **Company profiles.** A `CompanyProfile` from the optimizer can seed a provision, and the README can show the link: "scan this company, then book its provision."
- **Memos.** `tax-memo-writer` drafts the valuation-allowance or UTB memo from the computed schedules.
- **Workbook checks.** The workbook gets the same `verify_workbook.py` style recompute that gave you 1,457 / 0.
- **Real-company data: reuse `live.sec_tax_profile`.** It already turns SEC XBRL facts into pretax income, current/deferred federal/state/foreign tax, the valuation allowance, UTBs and cash taxes, with its own consistency checks. It is tested on a real Apple 10-K fixture (`tests/fixtures/aapl_10k_2026_tax_facts.json`). The provision skill reads 10-K disclosure data through it rather than through hand-typed figures. The only extension it needs is the ASU 2023-09 reconciliation concepts.

### Test strategy

1. **Fixtures modelled on published worked examples, without copying them.** The repo is public, and the best provision examples are copyrighted: the FASB Codification (including the ASC 740-10-55 illustrations), textbooks such as Kieso or Spiceland, and the Big 4 guides (PwC's Viewpoint *Income taxes*, Deloitte's *Roadmap: Income Taxes*). Free to read is not free to redistribute. IRS publications, by contrast, are U.S. government works and can be quoted, which is why #1 and #3 can use Pub. 505 and Pub. 590-B examples directly. So for #2:
   - **Re-parameterize.** For each published example you study, write your own fixture that uses the same *method* (the same kinds of permanent and temporary items, the same VA or loss-year pattern) with your own numbers, facts and wording. Work the expected answer yourself, in a spreadsheet you also commit.
   - **Cite, don't reproduce.** The test docstring names the method's source (for example "ASC 740-10-55, rate reconciliation illustration; structure only, numbers original"), with no copied tables, text or figures.
   - **Cross-check privately.** While you build, confirm that your engine reproduces the published answer on the original numbers locally. Keep those original-number checks out of the repo (for example a git-ignored `tests/private/` folder), and say in the README that this check was done.
   - **Anchor on primary sources you can publish:** IRC sections, the 21% rate, and the ASU 2023-09 category list and 5% rule, which you paraphrase in your own words with paragraph citations.
2. **A real 10-K disclosure test, and what it cannot prove.** A 10-K does not disclose the inputs `provision()` needs: item-by-item book-tax differences, credits before limits, and prior balances by item. So a 10-K **cannot** test the current or deferred computation. Checking that the company's own table foots would be circular, and the suite doesn't count that as a test. A 10-K does support two tests that can fail:
   - **Ingestion.** `sec_tax_profile` on the company's XBRL facts reproduces the reported current, deferred and total tax and the ETR. This extends the existing Apple fixture.
   - **A one-sided disclosure check, labeled a smoke test.** A 10-K only shows the lines the company chose to present. Items under 5% are already folded into category totals or "other", so the 10-K can't tell you what the classifier *should* have split out. That would repeat the circularity above. The classifier therefore works at **two levels**, and the test respects both:
     - **Category level.** The eight prescribed categories (state and local income tax net of federal effect; foreign tax effects; effect of changes in tax laws or rates enacted in the current period; effect of cross-border tax laws; tax credits; changes in valuation allowances; nontaxable or nondeductible items; changes in unrecognized tax benefits) are **"required" whenever the category's amount is nonzero, whatever its size**. The 5% test never removes a category line.
     - **Item level.** Inside foreign tax effects (by jurisdiction, then by nature), cross-border tax laws, tax credits and nontaxable or nondeductible items, and among "other adjustments", an item is **"required"** as its own line at or above 5% of statutory tax and is otherwise aggregated into its category (or "other"). A below-threshold item the company broke out anyway is **"voluntary"**, never "omit". State has its own qualitative rule (name the states that make up the majority of the state category), which the classifier flags as a text disclosure, not a number.

     Use a calendar-year PBE's **2025 10-K**, the first ASU 2023-09 year, and assert:
     - every nonzero prescribed category the company presents is classified "required", including a $40M "state, net of federal" line against a $105M threshold;
     - every presented item at or above the computed 5% threshold is "required";
     - each line maps to the same one of the eight categories as the company's caption;
     - a presented sub-item below the threshold, such as a $30M "nondeductible compensation" line under nontaxable or nondeductible items, is "voluntary", which is **not** a failure.

     This catches threshold arithmetic and category-mapping errors. It does not prove completeness, and the test's docstring says so.
   - **The completeness test uses synthetic fixtures**, where the full item list is known because you wrote it. Examples: items at 4.99% and 5.00% of the threshold base; several small items in one category that are each under 5% (the category line is still required, the items are aggregated); a state line at 1% of statutory tax (still required); a negative pretax income; a foreign jurisdiction line that must be disaggregated. Each expected classification cites the ASC 740-10-50 paragraph it relies on. The anchor fixture is your own re-parameterized version of the ASU 2023-09 illustrative example in ASC 740-10-55: same structure, original numbers.
   - The computation itself is proven by fixtures 1, 3 and 4, where every input is known.
3. **Invariants on every test:**
   - provision = current + deferred = reconciliation total;
   - **gross** deferred balances before the valuation allowance = Σ(cumulative temporary differences × the blended enacted rate) + NOL carryforwards × that rate + credit carryforwards at face value, where the blended rate is 21% + s × (1 − 21%) for the v1 state rate s (21% when s = 0); and **net** deferred balance = gross − VA. Credits are never multiplied by a rate: a $100,000 R&D credit carryforward is a $100,000 DTA;
   - roll-forward beginning + P&L + OCI + other = ending;
   - with zero temporary differences, deferred = 0;
   - the order of input items doesn't change any total.
4. **The worked example above** as a regression fixture, plus loss-year, NOL-with-naked-credit, OCI and both §174A-election variants.

### Sources and the parameters to verify before coding

- **GAAP standards:**
  - ASC 740-10, especially 740-10-25, -30 and -35-4, and the disclosure paragraphs 740-10-50-12A onward;
  - ASC 740-270 for interim periods, which is v2;
  - **ASU 2023-09**, effective for PBEs for annual periods beginning after Dec 15, 2024, and for other entities one year later. Verify the **eight prescribed categories** and exactly how the 5% threshold and jurisdiction disaggregation work, plus the income-taxes-paid disclosure (federal / state / foreign, and jurisdictions at 5% or more).
- **Tax law:**
  - IRC §11(b) (21%, unchanged by OBBBA), §172 (80%), §174/§174A and the IRS transition guidance (verify Rev. Proc. 2025-28);
  - §168(k) as amended by P.L. 119-21;
  - §250 NCTI and FDDEI deduction percentages for 2026 (verify the 40% and 33.34% figures before coding v1.1).
- **Mapping:** Schedule M-3 instructions, for the line mapping.

### Why it beats the alternatives

- **It is closest to what employers hire for.** Provision work is a large part of corporate and Big 4 tax work.
- **The gap is wide.** Existing provision skills are prose-only, and commercial provision software (ONESOURCE, Corptax, Longview) is closed.
- **It completes the business stack.** The optimizer finds planning; the provision books its financial-statement effect.
- **Its maintenance is real but schedulable.** Its law does change. ASU 2023-09 disclosures are new, the §174A transition elections and bonus vintages carry over for years, NCTI/FDDEI start in 2026, and UTBs and the blended state rate are inputs. But each change is a dated federal enactment or a FASB standard with an effective date, and the enactment-date design above stores it once with that date. Nexus, by contrast, changes state by state throughout the year (see "Why not the others"). That difference, together with reuse and employer value, is why #2 outranks nexus, not a claim that provision law is static. (The 21% rate in §11(b) has been permanent since the TCJA in 2017; OBBBA didn't change it, so it isn't a new reason for low maintenance.)

The trade-off is effort: it is the largest build. That's why it comes second, after #1 has proven the pattern.

---

## 3. `retirement-distribution-planner`

### The worked example

**Facts.** A married couple filing jointly in 2026, both age 74:
- $50,000 of Social Security;
- a $30,000 pension;
- one spouse's IRA was worth **$1,200,000 on Dec 31, 2025**.

**RMD.** The Uniform Lifetime divisor at age 74 is 25.5, so the RMD is **$47,058.82**.

**Baseline return** (engine: `taxable_social_security` → `form_1040`):
- taxable Social Security of $42,500 (the 85% cap);
- AGI of $119,558.82;
- a $12,000 senior deduction;
- taxable income of $72,058.82;
- **tax of $8,151.06** on the rate schedule; the filed return, which uses the Tax Table at this income, shows $8,153.

**Roth conversions.** I ran conversions through the engine. Each additional dollar costs:

| Conversion range (approx.) | Marginal cost | Why |
|---|---|---|
| $0 – $28,741.18 | 12% | 12% bracket (taxable income reaches $100,800) |
| $28,741.18 – $30,441.18 | 22% | 22% bracket, before the phase-out starts at $150,000 MAGI |
| $30,441.18 – $127,673.32 | **24.64%** | 22% bracket × 1.12, because the OBBBA senior deduction phases out at 6% per senior above $150K MAGI |
| $127,673.32 – $130,441.18 | 26.88% | 24% bracket (from $211,400 taxable income) × 1.12 |
| above $130,441.18 | 24% | Senior deduction is gone at $250,000 MAGI |

Each slope and breakpoint was checked by rerunning `compute_return` on either side of it.

**The IRMAA cliff.** Taxable Social Security is already at the 85% cap, so each converted dollar raises MAGI by one dollar. The first IRMAA tier is crossed at a conversion of **T − $119,558.82**, where T is the MFJ threshold for the premium year. Under the two-year lookback a 2026 conversion sets **2028** premiums, and the 2028 T isn't published yet, so the crossing is a **projection**:
- holding the 2026 threshold ($218,000): crossing at **$98,441.18**;
- an illustrative CPI-U path of 2.5% a year for two years, rounded as the statute requires (single threshold to the nearest $1,000, then doubled): about $230,000, crossing at about **$110,441**.

Either way, filling to the top of the 24.64% band (about $127.7K) crosses tier 1.

**What the example taught me:**
- **"Fill the 22% bracket" is the wrong rule in 2025–2028.** The 22% bracket really costs 24.64% for this couple, and filling it (about $127.7K) crosses the first IRMAA tier, which the projection puts somewhere between about $98K and $111K. The tool must find the cliffs, not just the bracket edges.
- **The thresholds that matter don't exist yet.** The 2028 IRMAA thresholds haven't been set. The tool must project them with a stated method, such as holding 2026 values or applying CPI-U, and label every result built on them as projected.
- **Ordering matters.** The RMD must be taken before any conversion. Withholding on an IRA distribution counts as paid evenly, which connects this tool to #1's year-end remedies.

### Edge cases the design must survive

| Edge case | Handling |
|---|---|
| **Born in 1959** (SECURE 2.0's drafting conflict between ages 73 and 75) | Follow the July 2024 proposed regulations, which use 73 for 1959 births and 75 for 1960 and later. Verify whether that has been finalized, and cite it in the output. |
| First RMD year | The first RMD can wait until April 1 of the next year, which puts two RMDs in one year. Model both options. |
| Spouse more than 10 years younger and the sole beneficiary | Use the Joint and Last Survivor table, not the Uniform table. |
| Still working, with a 401(k) | The still-working exception applies to the employer plan only, not to IRAs, and not to 5% owners. |
| Several IRAs versus several 401(k)s | IRA RMDs can be totaled and taken from any IRA; each 401(k) must take its own. |
| QCDs (age 70½ and over) | Reduce AGI, so they push back the IRMAA, Social Security and senior-deduction thresholds. Apply the indexed annual limit. |
| Social Security "tax torpedo" | Handled by calling `taxable_social_security` inside every scenario, never with a fixed 85%. |
| NIIT spillover | IRA distributions aren't NII, but they raise MAGI and can expose other investment income. Reuse `niit`. |
| Senior deduction sunset after 2028 | Multi-year projections drop it from 2029. |
| IRMAA appeal after a life-changing event (SSA-44) | Flag it; don't compute it. |
| Missed RMD | Show the §4974 excise: 25%, or 10% if corrected in time. |
| Inherited IRAs (10-year rule, annual RMDs) | **Out of scope for v1**, with a clear refusal in SKILL.md rather than a wrong answer. |

### Scope

Commands:
- `rmd(balance_prior_dec31, birth_date, spouse_birth_date=None, spouse_sole_beneficiary=False, plan_type="IRA", still_working=False)` returns the applicable age, the divisor, the RMD and the required beginning date.
- `rmd_schedule(...)` gives a multi-year projection with growth assumptions.
- `roth_conversion_scan(base_return, max_amount, step=500, ceilings=["bracket", "irmaa", "senior_phaseout", "niit"])` returns the marginal-cost map, the cliffs and the recommended ceiling for each objective. It runs the real 1040 in two passes:
  - a **coarse scan** at `step` dollars, which finds every interval where the marginal rate changes or a cliff (such as IRMAA) is crossed. That is about 260 `form_1040` runs for the $130K worked example.
  - **bisection** inside each flagged interval, down to $0.01. Each breakpoint takes about 16 more runs.

  The output breakpoints are exact to the cent **for the engine**, which uses the rate schedule (`rates.py`: "not the IRS tax table"). Form 1040 requires the Tax Table below $100,000 of taxable income, which taxes the midpoint of each $50 row. In the worked example all four breakpoints are at taxable income above $100,000, so they are also exact for the filed return. The baseline and the first part of the 12% band are not: at taxable income of $72,058.82 the Tax Table (row $72,050–$72,100, midpoint $72,075) gives **$8,153**, against the engine's $8,151.06. So the planner gets a `tax_method="table"` option, used by default when taxable income is under $100,000. It reports the filed-return tax, and the scanner treats the table's $50 steps as a staircase, not as breakpoints. A rate change narrower than `step` could hide between two coarse points, so the scan also checks that the average slope over each coarse interval matches the slopes at its ends, and bisects when it doesn't. That is how the $1,700-wide 22% band is caught even with a coarse step.
- `irmaa(magi, status, premium_year, projection=None)` returns the tier, the annual surcharge for Part B and Part D, and the distance to the next cliff. For a premium year whose thresholds aren't bundled, `projection` is required (`{"method": "hold", "from_year": 2026}`, `{"method": "cpi_u", "annual_rate": r}` or `{"method": "caller", "thresholds": [...]}`); without it the call raises. Every result built on a projection carries `"projected": true` and the method.

### How it reuses TaxKit

Almost entirely:
- `form_1040` for the return in every scenario;
- `taxable_social_security`, `senior_deduction`, `niit`, `standard_deduction` (65+ amounts) and `rates.bracket_breakdown`;
- the existing IRA and Roth limit functions in `retirement.py`, which this skill extends in the same module.

The new code is mostly tables (the Uniform Lifetime and Joint Life tables, IRMAA tiers) and a scanner loop.

### Test strategy

1. **Published examples.** Use the **Pub. 590-B** RMD examples and its Appendix B tables. Encode the **full** Uniform Lifetime table from Reg. §1.401(a)(9)-9(c) as a fixture and check every age. Use the **Pub. 915** Social Security worksheet examples. Check the IRMAA brackets against the CMS 2026 fact sheet.
2. **Scanner versus brute force, with each test claiming only what it can prove:**
   - **Default suite (fast).** For a few seeded random households, run a $1-step brute force in a ±$300 window around each breakpoint the scanner reports, and anywhere the coarse marginal rate changes. Assert that each scanner breakpoint falls inside the $1 interval where the brute force sees the rate change. A $1 search can only locate a breakpoint to within $1, so this test doesn't claim cents. That checks only what the scanner reported, so two more tests look for what it **missed**:
     - **An independent oracle.** From `params` alone, without calling the scanner, list every candidate breakpoint: each bracket edge, the senior-deduction phase-out start and end, the Social Security thresholds, the NIIT threshold and the IRMAA tiers, each converted to a conversion amount for the household. Open a ±$300 $1-step window around every candidate too. Assert that every rate change the brute force finds in any window appears in the scanner's output.
     - **A forced-coarse case.** Rerun the worked example with `step=5000`, wider than the $1,700 22% band, and assert the band is still found.
   - **Cent precision** is checked separately, because the tax is rounded to cents and a one-cent difference is too noisy to measure a slope. At each reported breakpoint *b*, the slope of `form_1040` tax over [*b* − $10, *b*] must equal the lower band's rate, and the slope over [*b*, *b* + $10] must equal the upper band's rate, within $0.01 / $10. If *b* were off by even $1, one of the two slopes would be a blend of both rates and the test would fail.
   - **Full-range brute force** at $1 steps over the whole range (about 130,000 runs per household) is marked `@pytest.mark.slow` and kept out of the default `pytest` run. It runs in a nightly CI job or before a release.
3. **The worked example** as a fixture: RMD of $47,058.82. Assert **all five** bands (12%, 22%, 24.64%, 26.88%, 24%) and all four breakpoints ($28,741.18, $30,441.18, $127,673.32, $130,441.18) to the cent, using the ±$0.01 check, plus the IRMAA crossing asserted as T − $119,558.82 for each projection method: $98,441.18 under `hold` from 2026, the CPI-U figure from the method's own rounding, and a caller-supplied T. Also assert that `irmaa(..., premium_year=2028)` with no `projection` raises, and that every projected output is labelled. A scanner that merges the narrow 22% band into its neighbors must fail.
4. **Boundaries:** birth years 1950, 1951, 1959 and 1960; the April 1 double RMD; QCD at the limit and $1 over it.
5. **Tax Table mode:** $8,153 at taxable income $72,058.82; taxable income of $99,999 uses the table and $100,000 uses the schedule; every Tax Table row is checked against the IRS table for at least one sampled midpoint per $5,000.

### Sources and the parameters to verify before coding

- **Statutes:** IRC §401(a)(9) (as amended by SECURE 2.0 §107), §408(d)(8) (QCD, indexed under SECURE 2.0), §86, §4974 and §151(d)(5).
- **Regulations:** Reg. §1.401(a)(9)-9 tables, and the 2024 final and proposed RMD regulations.
- **Medicare:** 42 U.S.C. §1395r(i) and 20 CFR Part 418 (IRMAA).
- **Parameters to verify:**
  - 2026 IRMAA tiers, which start at **$109,000 / $218,000** based on 2024 MAGI;
  - the 2026 Part B premium and the Part D surcharges, from the CMS fact sheet;
  - the 2026 QCD limit, from the IRS release;
  - the senior deduction of $6,000, phasing out at 6% above $75,000 / $150,000 MAGI (2025–2028), per the Schedule 1-A instructions;
  - the per-person phase-out reading the engine uses.
- Your 2026 brackets and standard deduction already follow Rev. Proc. 2025-32.

### Why it beats the alternatives

It has the highest engine reuse of any candidate. The market has commercial planners (Holistiplan, Income Lab), but no open, tested Claude skill. The OBBBA senior deduction gives it a timely, non-obvious result: the effective rate in the 22% bracket is 24.64%. Its parameters update on the same yearly cycle as `params.py`, and it shares the withholding and payment logic with #1.

---

## Why not the others

| Candidate | Why it lost |
|---|---|
| **Sales-tax economic nexus and apportionment** (4th) | **Data drift.** It needs a 46-jurisdiction table where each cell is its own legal question: gross vs. retail vs. taxable sales, marketplace sales included or not, calendar-year vs. rolling 12 months (Illinois is measured quarterly over 12 months; New York over four sales-tax quarters). Those rules change throughout the year. The survey's own Kentucky change is still only "reported". **No reuse:** it touches none of your federal engine. **The worst failure costs the most:** a false "no nexus" leaves the seller owing uncollected tax out of pocket. **Free tools already exist:** Avalara and TaxJar publish free nexus charts. Build it fifth or later, or now as a limited version covering your top ten states, if you're aiming at SALT roles. |
| **Document intake and K-1 analyzer** | Extraction is model or OCR work, not deterministic Python. The checkable part is thin (W-2 box 4 = 6.2% × box 3, capped at the wage base; box 6 = 1.45% × box 5) and fits better as an input validator inside #1. Test fixtures are realistic tax documents, which is a privacy risk in a public repo. |
| **Crypto tax lots** | The most crowded niche, and it adds nothing to an accounting profile. |
| **Form 709 / estate tax** | Narrow demand for an entry-level candidate. The OBBBA $15M exemption makes few clients taxable. |
| **Form 1041 / DNI** | Hard to get right (tier system, separate share rule) for a small audience. A good v3 after #3. |
| **Return-review diff and CP2000 recompute** | Both depend on the document intake above. Revisit once you have an intake layer. |
| **International information returns** | Mostly penalty and filing logic with little calculation, and high liability if wrong. |

---

## Build order and effort

The estimates below are itemized against every feature in each skill's scope, and parameter verification is its own line item, not taken from slack. They assume 12 hours a week, starting the week of November 30, 2026.

**Shared plumbing: 8 h (week 1).** This is based on how `scripts/build_skills.py` actually works today: `vendor()` copies the **whole** `src/taxkit` package into every code skill, the script imports only `taxkit.business` to register commands, `main()` writes `commands.md` for only the two existing skills, and the calculator's group list is made by filtering out the single group "Business optimizer".
**The rule: week 1 builds the mechanism, and each release adds its own module.** A package is listed in the add-on registry only in the same commit that creates it. Listing all three in week 1 would break every command: `api.main()` calls `_load_optional_modules()` first, so an unconditional import of a `taxkit.provision` that won't exist until week 6 would make `api list`, `form_1040` and the optimizer raise `ModuleNotFoundError`, and `build_skills.py` would fail to rebuild anything. Every release must leave `main` green.

- `api.py`: add a single registry `ADDONS = ("taxkit.business",)` and have `_load_optional_modules` loop over it with no `try/except` (diff below). Add a test parameterized over `ADDONS` that imports each module and checks `api list` contains its commands. It passes in week 1 with one entry and gains a case automatically each release: 1 h.
- `build_skills.py`, restructured so a release only adds data: 4 h.
  - Import add-ons by looping over `api.ADDONS` instead of the hard-coded `import taxkit.business`, so the script never names a package that isn't there yet.
  - Replace the one-group filter with an explicit allowlist per skill, `SKILL_GROUPS = {"us-tax-calculator": CORE, "business-tax-optimizer": CORE + ["Business optimizer"]}`, where `CORE` is today's calculator list. Write each skill's `commands.md` in one loop over `SKILL_GROUPS`, and build `CODE_SKILLS` from its keys. In week 1 this produces byte-identical output for the two existing skills, which `--check` confirms.
- A `test_skills.py` check that each built bundle's `commands.md` lists exactly its allowlisted commands, plus `build_skills.py --check` in CI: 2 h.
- Set up the `slow` pytest marker and a nightly CI job: 1 h.

**Each release then adds, in one commit** (about 30 minutes, counted in that skill's "SKILL.md and packaging" line):
- v0.4: create `taxkit/estimates/`; append `"taxkit.estimates"` to `ADDONS`; add group "Estimated tax" to `GROUPS` and `"estimated-tax-planner": CORE + ["Estimated tax"]` to `SKILL_GROUPS`; add an entry script `estimate.py` copied from `tax.py`.
- v0.5: the same for `taxkit.provision`, group "Income tax provision", skill `tax-provision-740`, `provision.py`.
- v0.6: the same for `taxkit.retire`, group "Retirement distributions" (the existing group "Retirement" keeps its name), skill `retirement-distribution-planner`, `retire.py`.

Before each tag, run the release gate: `python -m taxkit.api list`, the full test suite and `build_skills.py --check` on a clean checkout. The v0.4 cut-line release in late December therefore ships a working API with exactly two add-ons.

Because every bundle carries the full package, each new skill adds about 0.3 MB (today's vendored `taxkit` is 324 KB). That is acceptable. A command outside a skill's allowlist still runs if called, but it isn't documented, so the model won't reach for it.

There is no new rate table: #1 calls `live.underpayment_rate`.

**#1 `estimated-tax-planner`: 58 h (weeks 1–6).**

| Item | Hours |
|---|---|
| Verify parameters (rates, dates, Schedule AI factors, prorated bases) | 4 |
| `safe_harbor`, with `withholding` and `citizen_or_resident` inputs for the §6654(e)(1)/(2) exceptions, the `prior_year` dict (own status, spouse's separate tax) for MFJ/MFS allocation, §6654(h), and the short or missing prior year | 6 |
| Penalty ledger: day splits at rate changes, the §7503 holiday table, §7508A windows, farmer/fisherman rule, overpayment credit, actual withholding dates | 9 |
| Schedule AI Parts I and II, with recapture, plus the `payroll.se_components` refactor | 12 |
| `year_end_projection` with four remedies, IRA withholding rate (10% default / W-4R election), rollover cash and 12-month checks, and §72(t) | 8 |
| `estimate_vouchers` | 1 |
| Form 2210 Part III/IV sheet with live formulas | 5 |
| Boundary tests for the 14 edge-case rows, and property tests | 6 |
| Transcribe the Pub. 505 and Form 2210 worked examples as fixtures | 3 |
| Head-to-head eval against the flat-22% skill | 1 |
| SKILL.md and packaging | 3 |

- **Cut line.** If the work runs late, v0.4 ships with the safe harbor, the ledger, the regular-method projection with the W-4 and Jan 15 remedies, the tests for those parts and the SKILL.md. That is about 36 hours, which with the 8 hours of plumbing puts it at about December 26. Schedule AI, the IRA remedies and the 2210 sheet follow in v0.4.1.
- **The Jan 15, 2027 date is safe either way.** Plumbing plus the full skill is 66 hours. There are 72 working hours between November 30 and January 10, so the full skill fits with 6 hours to spare, and the cut-line release fits with weeks to spare. The deadline is a good moment to post on LinkedIn.

**#2 `tax-provision-740`: 92 h (weeks 6–14). Release v0.5.**

| Item | Hours |
|---|---|
| Verify the standards: ASU 2023-09 categories, the 5% rule, jurisdiction disaggregation, income taxes paid | 6 |
| `provision` core: current and deferred tax, sign conventions, enactment-date check | 12 |
| `deferred_rollforward`, with OCI and other-movement columns | 8 |
| `rate_reconciliation`: the two-level classifier (categories required when nonzero; items at 5%), PBE and non-PBE versions, loss-year handling | 10 |
| `va_sources_of_income`, with the 80%-limited naked-credit capacity | 8 |
| UTB roll-forward and its reconciliation line | 4 |
| `provision_workbook`, plus its `verify_workbook` recompute | 12 |
| Extend `sec_tax_profile` with the ASU 2023-09 XBRL concepts, and the 10-K smoke test | 6 |
| Fixtures: original re-parameterized versions of the ASC 740-10-55, textbook and Big 4 guide examples (worked answers in a committed spreadsheet), private original-number cross-checks, synthetic 5%-boundary sets | 12 |
| Invariant and property tests (gross-before-VA deferred identity, credits at face, blended rate) | 6 |
| SKILL.md and the link to the memo skill | 4 |
| Buffer for the most error-prone part (provision core and reconciliation) | 4 |

- **Out of v1:** `schedule_m3_map` (about 6 h) and the §250 NCTI/FDDEI computation go into v1.1.
- **Cut line:** the provision core, roll-forward and reconciliation, with their tests and the SKILL.md, are about 62 hours, so they can ship by about week 12. The VA schedule and the workbook would then follow in v0.5.1.

**#3 `retirement-distribution-planner`: 49 h (weeks 14–18). Release v0.6.**

| Item | Hours |
|---|---|
| Verify parameters (IRMAA, Part B and Part D, QCD limit, senior deduction, the 1959 rule) | 4 |
| `rmd`, with the full Uniform and Joint Life tables and the edge cases | 8 |
| `rmd_schedule` | 3 |
| `irmaa`, with tiers and the `hold` / `cpi_u` / `caller` projection methods | 5 |
| `roth_conversion_scan`: coarse scan, slope check, bisection | 10 |
| Windowed brute-force tests (scanner and independent-oracle windows), the forced-coarse case, the cent-precision test and the slow full-range test | 4 |
| `tax_method="table"` (Tax Table below $100,000) and its tests | 3 |
| Worked-example fixture and boundary tests | 5 |
| Links to #1 | 2 |
| SKILL.md and packaging | 5 |

**Total: 8 + 58 + 92 + 49 = 207 hours, about 17–18 weeks at 12 hours a week.** I add a separate **31-hour contingency (15%)**, which brings it to about 238 hours, or about 20 weeks. That means finishing around late April 2027. The contingency isn't assigned to any task. If one skill overruns, take the overrun from the contingency first, then fall back to that skill's cut line, so the next skill's start date doesn't slip.

Change needed in `src/taxkit/api.py` in week 1. Every bundle carries the whole package, so every module listed in `ADDONS` is present in every bundle, and an import failure is a real bug that should be raised rather than letting the add-on's commands quietly disappear. That is safe only because `ADDONS` lists packages that already exist; it starts with one entry and grows by one per release.

```diff
+# Add-on packages that register their own commands. Append a package here only in the
+# commit that creates it (v0.4: taxkit.estimates, v0.5: taxkit.provision, v0.6: taxkit.retire).
+ADDONS = ("taxkit.business",)
+
 def _load_optional_modules():
-    try:  # the business optimizer registers its own commands when present
-        import importlib
-        importlib.import_module("taxkit.business")
-        # When run as ``python -m taxkit.api`` this module is __main__, a different object from
-        # ``taxkit.api`` (where add-ons register), so merge the registries.
-        COMMANDS.update(importlib.import_module("taxkit.api").COMMANDS)
-    except ImportError:
-        pass
+    import importlib
+    for mod in ADDONS:
+        importlib.import_module(mod)  # every listed add-on exists, so a failure is a real bug: raise it
+    # When run as ``python -m taxkit.api`` this module is __main__, a different object from
+    # ``taxkit.api`` (where add-ons register), so merge the registries.
+    COMMANDS.update(importlib.import_module("taxkit.api").COMMANDS)
```

### Checklist before writing code for each skill
- [ ] Every "verify" parameter above is checked against its primary source and entered with its source string.
- [ ] No future value is guessed. Unbundled rates (2027 §6621) come in as labeled overrides or raise an error, and projected values (2028 IRMAA) carry the caller's stated method, with fixtures asserting the formula, not one projected number.
- [ ] Any cent-level claim says whether it is the engine (rate schedule) or the filed return (Tax Table below $100,000).
- [ ] Each row of the edge-case table has a test, including the exact boundary.
- [ ] At least one published worked example backs a fixture, and its cited page or paragraph is in the test docstring. IRS examples may be used as published. Copyrighted examples (FASB, textbooks, Big 4 guides) are re-parameterized with original numbers and wording, and the original-number checks stay out of the public repo.
- [ ] SKILL.md lists what the skill **refuses** (CAMT, inherited IRAs, multistate provisions) so the model doesn't improvise those.
