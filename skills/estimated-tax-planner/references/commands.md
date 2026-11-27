# Command reference

Run `python scripts/estimate.py <command> '<json>'`. Arguments not listed as required are optional.

## Estimated tax

### `safe_harbor`

Required annual payment under IRC 6654(d) and the four installments, with the 6654(e) exceptions.

Args: `current_tax`=**required**, `withholding`=**required**, `status`=**required**, `year`=2026, `prior_year`=None, `citizen_or_resident`=True, `farmer_fisherman`=False, `filed_and_paid_by_jan31`=False

### `underpayment_penalty`

Form 2210 regular-method penalty.

Args: `required_installments`=**required**, `payments`=**required**, `withholding`=0.0, `year`=2026, `withholding_dates`=None, `rate_overrides`=None, `rate_assumption`=None, `postponements`=None

### `year_end_projection`

Project the year's tax with the full Form 1040 engine and rank the ways to avoid the penalty.

Args: `return_inputs`=**required**, `estimated_payments`=None, `as_of`="", `prior_year`=None, `has_wages`=True, `taxpayer_age`=None, `ira`=None, `citizen_or_resident`=True, `rate_overrides`=None, `rate_assumption`=None

### `estimate_vouchers`

Form 1040-ES amounts: (required annual payment - expected withholding) split over the due dates.

Args: `required_annual_payment`=**required**, `expected_withholding`=0.0, `year`=2026, `farmer_fisherman`=False

### `installment_due_dates`

The four 1040-ES due dates for ``year`` (Apr 15, Jun 15, Sep 15, Jan 15), shifted by IRC 7503. Farmers and fishermen pay one installment, on Jan 15 (IRC 6654(i)).

Args: `year`=**required**, `farmer_fisherman`=False

## Rates & returns

### `income_tax`

Income tax with preferential rates under IRC 1(h) (the Schedule D Tax Worksheet).

Args: `taxable_income`=**required**, `status`=**required**, `year`=2026, `qualified_dividends`=0.0, `net_ltcg`=0.0, `unrecaptured_1250`=0.0, `collectibles_gain`=0.0, `method`="law"

### `ordinary_tax`

Regular tax from the rate schedule (not the IRS tax table).

Args: `taxable_income`=**required**, `status`=**required**, `year`=2026

### `bracket_breakdown`

Bracket-by-bracket table.

Args: `taxable_income`=**required**, `status`=**required**, `year`=2026

### `per_band_min_tax`

The simplified method: split income at every ordinary *and* capital-gain breakpoint and tax each preferential slice at the smaller of the ordinary and capital-gain rate for that slice.

Args: `taxable_income`=**required**, `preferential_income`=**required**, `status`=**required**, `year`=2026

### `form_1040`

Complete Form 1040. Some amounts are entered twice on purpose, as on the real form: ``ordinary_dividends`` INCLUDES ``qualified_dividends``; ``net_capital_gain`` is the Schedule D net (a loss is limited to -3,000) and ``net_ltcg_for_rates`` is the part eligible for 0/15/20%; ``net_investment_income`` (for NIIT) is not derived automatically.

Args: `year`=2026, `status`="S", `method`="law", `wages`=0.0, `taxable_interest`=0.0, `ordinary_dividends`=0.0, `qualified_dividends`=0.0, `net_capital_gain`=0.0, `net_ltcg_for_rates`=0.0, `schedule_c_profit`=0.0, `se_person_wages`=None, `other_income`=0.0, `taxable_social_security`=0.0, `se_health_insurance`=0.0, `se_retirement`=0.0, `ira_deduction`=0.0, `student_loan_interest`=0.0, `educator_expenses`=0.0, `alimony_paid`=0.0, `other_adjustments`=0.0, `itemized`=<factory>, `age65_or_blind_boxes`=0, `num_seniors`=0, `qualified_tips`=0.0, `qualified_overtime`=0.0, `car_loan_interest`=0.0, `other_qbi`=0.0, `qbi_override`=None, `qbi_w2_wages`=None, `qbi_ubia`=0.0, `qbi_sstb`=False, `qbi_active`=True, `qualifying_children`=0, `other_dependents`=0, `other_credits`=0.0, `eitc`=0.0, `net_investment_income`=0.0, `withholding`=0.0, `estimated_payments`=0.0

### `params`

Look up tax-year parameters. With ``key`` returns one value; otherwise every parameter (status-dependent ones for ``status`` if given, else all statuses) with its source.

Args: `year`=2026, `status`=None, `key`=None

## Payroll

### `fica`

FICA on W-2 wages for one employee.

Args: `wages`=**required**, `status`="S", `year`=2026, `other_wages_same_return`=0.0

### `self_employment_tax`

Schedule SE for one person.

Args: `se_income`=**required**, `status`="S", `year`=2026, `w2_wages`=0.0, `medicare_wages_on_return`=None

### `niit`

Net investment income tax: 3.8% x lesser of NII or MAGI over threshold.

Args: `net_investment_income`=**required**, `magi`=**required**, `status`="S", `year`=2026

## Retirement

### `traditional_ira_deduction`

Deductible traditional IRA contribution. Phase-out applies if the taxpayer is covered, or (MFJ) only the spouse is covered. A partially phased-out deduction is rounded up to $10 with a $200 minimum.

Args: `contribution`=**required**, `magi`=**required**, `status`=**required**, `covered_by_plan`=**required**, `spouse_covered`=False, `compensation`=1000000000000.0, `age`=30, `year`=2026

### `roth_contribution_limit`



Args: `magi`=**required**, `status`=**required**, `compensation`=1000000000000.0, `age`=30, `year`=2026

### `sep_deduction`

SEP-IRA for a self-employed person.

Args: `net_se_income`=**required**, `half_se_tax`=0.0, `year`=2026, `use_shortcut`=None, `method`="simplified"

## Live data

### `sec_tax_profile`

Build a checked income tax profile from us-gaap XBRL facts (one 10-K carries ~3 years).

Args: `facts`=**required**, `company`="", `source`="SEC XBRL (10-K)", `as_of`="", `statutory_rate`=0.21

### `underpayment_rate`

Rate for 'YYYYQn', with a live override (e.g. fetched from irs.gov) taking precedence.

Args: `quarter`=**required**, `overrides`=None
