# Command reference

Run `python scripts/tax.py <command> '<json>'`. Arguments not listed as required are optional.

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

## Individual

### `standard_deduction`

Standard deduction.

Args: `status`=**required**, `year`=2026, `age65_or_blind_boxes`=0, `is_dependent`=False, `earned_income`=0.0, `spouse_itemizes_mfs`=False

### `senior_deduction`

OBBBA $6,000 deduction per individual age 65+, phased out at 6%.

Args: `num_seniors`=**required**, `magi`=**required**, `status`=**required**, `year`=2026

### `tips_deduction`

No tax on tips: up to $25,000, reduced $100 per $1,000 over $150K/$300K.

Args: `qualified_tips`=**required**, `magi`=**required**, `status`=**required**, `year`=2026

### `overtime_deduction`

No tax on overtime premium: $12,500 / $25,000 MFJ.

Args: `qualified_overtime`=**required**, `magi`=**required**, `status`=**required**, `year`=2026

### `car_loan_interest_deduction`

Qualified passenger vehicle loan interest: up to $10,000.

Args: `interest`=**required**, `magi`=**required**, `status`=**required**, `year`=2026

### `child_tax_credit`

CTC ($2,200) + ODC ($500), phase-out $50 per $1,000 over $200K/$400K; refundable ACTC = lesser of $1,700/child, unused credit, or 15% x (earned - $2,500). With 3+ qualifying children, Schedule 8812 Part II-B lets the 15% amount be replaced by the larger of it or (employee Social Security and Medicare taxes + 1/2 SE tax - EITC).

Args: `qualifying_children`=**required**, `other_dependents`=**required**, `magi`=**required**, `status`=**required**, `tax_before_credits`=**required**, `earned_income`=**required**, `year`=2026, `payroll_taxes_paid`=0.0, `eitc`=0.0

### `kiddie_tax`

Form 8615 simplified (one child, no preferential income, no itemizing).

Args: `earned_income`=**required**, `unearned_income`=**required**, `parent_taxable_income`=**required**, `parent_status`=**required**, `year`=2026

### `taxable_social_security`

IRC 86 two-tier inclusion. MFS living with spouse: base amounts are 0.

Args: `benefits`=**required**, `magi_without_ss`=**required**, `tax_exempt_interest`=**required**, `status`=**required**

### `qbi_deduction`

Lesser of 20% x QBI or 20% x (TI before QBI - net capital gain incl. QD), plus the 2026+ $400 minimum for at least $1,000 of active QBI. Simplified: assumes the W-2 wage / UBIA and SSTB limits don't bind - above the threshold use :func:`qbi_deduction_full`.

Args: `qbi`=**required**, `taxable_income_before_qbi`=**required**, `net_capital_gain`=**required**, `status`=**required**, `year`=2026, `active`=True

## Itemized deductions

### `itemized_deductions`



Args: `agi`=**required**, `status`=**required**, `year`=2026, `medical_expenses`=0.0, `state_local_taxes`=0.0, `mortgage_interest`=0.0, `mortgage_avg_balance`=0.0, `investment_interest`=0.0, `net_investment_income`=0.0, `charity_cash_public`=0.0, `charity_property_public`=0.0, `charity_cash_private`=0.0, `charity_property_private`=0.0, `casualty_loss_allowed`=0.0, `gambling_losses`=0.0, `gambling_winnings`=0.0, `other`=0.0, `magi`=None

### `salt_cap`

OBBBA SALT cap: $40,000 (2025) / $40,400 (2026), reduced 30% of MAGI over $500K / $505K, never below $10,000 ($5,000 MFS).

Args: `magi`=**required**, `status`=**required**, `year`=2026

### `charitable_deduction`

Simplified IRC 170(b) ordering: each bucket limited to its %-of-AGI cap and the total limited to 60% of AGI. 2026+: only the excess over 0.5% of AGI is deductible. Property amounts are FMV for LTCG property; use basis for ordinary-income / short-term property.

Args: `agi`=**required**, `cash_public`=0.0, `property_ltcg_public`=0.0, `cash_private`=0.0, `property_ltcg_private`=0.0, `year`=2026

### `mortgage_interest_deduction`

Pro-rate interest when acquisition debt exceeds $750K ($1M if pre-12/16/2017).

Args: `interest_paid`=**required**, `average_balance`=**required**, `status`=**required**, `year`=2026, `grandfathered`=False

### `medical_deduction`



Args: `expenses`=**required**, `agi`=**required**, `year`=2026

### `gambling_loss_deduction`

2026+: 90% of losses, capped at winnings (OBBBA).

Args: `losses`=**required**, `winnings`=**required**, `year`=2026

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

## Property

### `amount_realized`

Money + FMV of property + liabilities assumed by buyer - selling expenses.

Args: `cash`=0.0, `fmv_property_received`=0.0, `debt_relief`=0.0, `selling_expenses`=0.0

### `adjusted_basis`

Cost + capital improvements - depreciation/cost recovery. Repairs are NOT added.

Args: `original_cost`=**required**, `improvements`=0.0, `cost_recovery`=0.0

### `sale`

Realized vs recognized gain. Losses on personal-use assets are not recognized.

Args: `amount_realized_`=**required**, `adjusted_basis_`=**required**, `personal_use`=False, `sec121_exclusion`=0.0

### `home_sale_exclusion`

Sec. 121: $250K / $500K if owned AND used 24 of the last 60 months. Reduced exclusion (months/24) for health, job change or unforeseen events.

Args: `status`=**required**, `year`=2026, `months_owned`=24, `months_used`=24, `partial_reason`=False

### `net_capital_gains`

Net ST and LT separately, offset across, apply the $3,000 ($1,500 MFS) limit, and carry the rest forward keeping its character. Pass losses and carryovers as positive numbers.

Args: `st_gains`=0.0, `st_losses`=0.0, `lt_gains`=0.0, `lt_losses`=0.0, `st_carryover`=0.0, `lt_carryover`=0.0, `status`="S", `year`=2026, `taxable_income`=None

### `foreclosure`

Recourse: gain = FMV - basis, COD income = debt - FMV. Non-recourse: treated as a sale for the full debt; gain = debt - basis.

Args: `debt`=**required**, `basis`=**required**, `fmv`=**required**, `recourse`=**required**

### `gift_basis`

Dual-basis rule: if FMV < donor basis at gift, use FMV for losses and donor basis for gains (no gain/loss in between).

Args: `donor_basis`=**required**, `fmv_at_gift`=**required**, `sale_price`=**required**

### `converted_property_basis`

Personal-use asset converted to business use: depreciable basis is the lower of adjusted basis or FMV.

Args: `adjusted_basis_`=**required**, `fmv_at_conversion`=**required**

## Entities

### `owner_reporting`

What the owner reports when the business has deducted the owner's "salary"

Args: `entity`=**required**, `book_net_income`=**required**, `owner_salary_deducted`=**required**, `distributions`=0.0, `ownership_pct`=1.0, `general_partner`=True, `has_basis`=True

### `basis_rollforward`

Partner / S corp outside basis year by year (lists of equal length).

Args: `contributions`=**required**, `net_income`=**required**, `distributions`=**required**, `ownership_pct`=1.0, `beginning_basis`=0.0

### `c_corp_tax`

Form 1120 simplified. ``gross_income`` excludes ``dividends_received``. Dividends the corporation *pays* are not deductible (double taxation). DRD taxable-income limitation is applied (50%/65% DRD limited to that % of TI). ``method="simplified"`` uses the pre-2018 70%/80%/100% DRD.

Args: `gross_income`=**required**, `deductions`=**required**, `dividends_received`=0.0, `ownership_pct_of_payer`=0.0, `charitable_contributions`=0.0, `nol_carryforward`=0.0, `year`=2026, `drd_rates`=None, `method`="law"

### `double_tax_burden`

Combined corporate + shareholder tax if all after-tax profit is distributed.

Args: `pretax_corp_income`=**required**, `shareholder_dividend_rate`=**required**, `year`=2026

## Depreciation & amortization

### `macrs_table`

Percentages (e.g. 20.0 means 20%) for each recovery year.

Args: `recovery_class`=**required**, `convention`="HY"

### `personal_property_schedule`

Full schedule: cost x business-use -> Sec. 179 -> bonus on remainder -> MACRS on the rest. If disposed, the disposal year gets half (HY) or the mid-quarter fraction.

Args: `cost`=**required**, `recovery_class`=**required**, `convention`="HY", `sec179`=0.0, `bonus_pct`=0.0, `business_use_pct`=1.0, `disposed_in_year`=None, `disposal_quarter`=None

### `real_property_depreciation`

Straight-line, mid-month convention: 27.5 years (330 months) residential, 39 years (468 months) nonresidential. Land is never depreciated.

Args: `cost_of_building`=**required**, `month_placed`=**required**, `residential`=True, `years`=3, `month_disposed`=None, `disposal_year`=None

### `sec179_allowed`

Sec. 179: limit reduced $-for-$ above the phase-out threshold and limited to business taxable income (excess carries forward). Returns (deduction, carryforward).

Args: `cost_placed_in_service`=**required**, `total_179_property_year`=**required**, `elected`=**required**, `business_taxable_income`=None, `year`=2026

### `needs_mid_quarter`

Mid-quarter applies if > 40% of the year's personal property (excluding real property and Sec. 179 amounts) is placed in service in Q4.

Args: `q4_cost`=**required**, `total_cost`=**required**

### `startup_costs`

Deduct up to $5,000 (reduced $-for-$ over $50,000), amortize the rest over 180 months. Returns (first-year deduction, annual amortization thereafter).

Args: `total`=**required**, `months_in_first_year`=**required**, `year`=2026

### `sec197_amortization`

Sec. 197 intangibles (goodwill, covenants, etc.): 15 years straight-line.

Args: `cost`=**required**, `months_in_first_year`=**required**

### `cost_depletion`

Basis / remaining recoverable units x units sold.

Args: `adjusted_basis`=**required**, `units_sold`=**required**, `estimated_remaining_units`=**required**

### `percentage_depletion`

Statutory % of gross income, limited to 50% of taxable income before depletion.

Args: `gross_income`=**required**, `rate`=**required**, `taxable_income_before_depletion`=**required**

## Income items

### `imputed_interest`

Below-market loan rules (IRC 7872).

Args: `loan_amount`=**required**, `afr`=**required**, `stated_rate`=**required**, `loan_type`="gift", `borrower_nii`=0.0, `months`=12

### `annuity_exclusion`

Exclusion ratio = investment / expected return; once the investment is fully recovered, every payment is taxable. ``expected_return_multiple`` comes from Reg. 1.72-9 Table V (e.g. 20.0 at age 65).

Args: `investment`=**required**, `monthly_payment`=**required**, `expected_return_multiple`=**required**, `years_received_so_far`=0.0

### `group_term_life_income`

Taxable cost of employer group-term life over $50,000 (Table I).

Args: `coverage`=**required**, `age`=**required**, `employee_paid`=0.0, `months`=12, `year`=2026

### `feie`

Foreign earned income exclusion, prorated by qualifying days.

Args: `foreign_earned_income`=**required**, `qualifying_days`=**required**, `year`=2026, `days_in_year`=365

### `ltc_taxable`

Per-diem LTC benefits: excludable = max(per diem limit x days, actual cost) - other reimbursements; excess benefits are income.

Args: `total_cost`=**required**, `days`=**required**, `insurance_received`=**required**, `medicare_paid`=0.0, `year`=2026

### `scholarship_taxable`

Only qualified tuition/fees/books are excluded; room and board is taxable.

Args: `total_received`=**required**, `tuition_fees_books`=**required**

### `oid_accrual`

Annual compounding interest that must be reported each year even though it is paid at maturity.

Args: `principal`=**required**, `annual_rate`=**required**, `years`=**required**

### `tax_benefit_refund_income`

State refund is income only to the extent the prior deduction gave a benefit.

Args: `state_refund`=**required**, `itemized_claimed`=**required**, `standard_deduction_then`=**required**, `itemized_prior_year`=True

## Losses

### `casualty_loss`

Casualty loss.

Args: `adjusted_basis`=**required**, `fmv_before`=**required**, `fmv_after`=**required**, `insurance`=**required**, `agi`=**required**, `personal`=True, `completely_destroyed_business`=False, `qualified_disaster`=False, `year`=2026

### `excess_business_loss`

IRC 461(l): business losses above the threshold become an NOL carryforward.

Args: `business_income`=**required**, `business_deductions`=**required**, `status`=**required**, `year`=2026

### `apply_nol`

Post-2017 NOLs: deduction limited to 80% of taxable income before the NOL.

Args: `taxable_income_before_nol`=**required**, `nol_carryforward`=**required**, `year`=2026

### `compute_nol`

Individual NOL: start with (negative) taxable income, remove net capital gains, add back the standard/itemized deduction, remove non-business income. Returns the NOL as a positive number.

Args: `taxable_income`=**required**, `net_capital_gain_included`=**required**, `std_or_itemized_deduction`=**required**, `nonbusiness_income`=**required**, `nonbusiness_deductions_other`=0.0

### `vacation_home`

IRC 280A.

Args: `rental_days`=**required**, `personal_days`=**required**, `gross_rent`=**required**, `mortgage_interest`=**required**, `property_taxes`=**required**, `operating_expenses`=**required**, `depreciation`=**required**, `direct_rental_expenses`=0.0, `method`="tax_court"

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

## Output

### `workbook`

Generate the formula-driven Excel / Google Sheets workbook (requires openpyxl).

Args: `out`="TaxKit.xlsx"
