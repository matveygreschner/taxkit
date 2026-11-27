# Company profile fields

Pass these to `business_scan` as `{"profile": {...}}`. All are optional; unknown amounts default to zero, so checks that need them simply don't apply.

| Field | Default | Meaning |
|---|---|---|
| `name` | 'Company' |  |
| `year` | 2026 |  |
| `entity_type` | 's_corp' | sole_prop | partnership | s_corp | c_corp |
| `industry` | '' |  |
| `sstb` | False | specified service business (health, law, accounting, consulting, financial services...) |
| `avg_gross_receipts_3yr` | 0.0 | 3-year average gross receipts (Sec. 448(c) test) |
| `avg_gross_receipts_5yr` | None |  |
| `is_tax_shelter` | False |  |
| `current_year_gross_receipts` | 0.0 |  |
| `years_with_receipts` | 10 |  |
| `net_income_before_owner_pay` | 0.0 | profit after ordinary expenses (incl. domestic R&D, which is expensed by default) but BEFORE owner salary/guaranteed payments and BEFORE depreciation on the assets and building listed in this profile |
| `owner_salary` | 0.0 | W-2 salary to the owner (S/C corp) or guaranteed payments (partnership) |
| `owner_filing_status` | 'MFJ' |  |
| `owner_other_income` | 0.0 |  |
| `owner_other_salt` | 0.0 | owner's property tax + other state/local taxes (for the SALT cap / PTET math) |
| `num_owners` | 1 |  |
| `employees` | 0 |  |
| `non_owner_wages` | 0.0 | W-2 wages to employees other than the owner |
| `ubia` | 0.0 | unadjusted basis of qualified property (Sec. 199A) |
| `state_income_tax_rate` | 0.0 | flat state income tax rate on business income (illustrative) |
| `state_has_ptet` | True |  |
| `uses_accrual_method` | False |  |
| `accounts_receivable` | 0.0 |  |
| `accounts_payable_and_accruals` | 0.0 |  |
| `assets` | [] |  |
| `building_cost_placed_in_service` | 0.0 |  |
| `building_is_residential` | False |  |
| `building_used_in_production` | False | building houses manufacturing/production (Sec. 168(n) candidate) |
| `building_production_share` | 1.0 |  |
| `building_original_use` | True | false if the building was bought used |
| `building_construction_began_after_jan19_2025` | True |  |
| `cost_seg_reclass_pct` | 0.25 |  |
| `domestic_research_expenses` | 0.0 |  |
| `unamortized_domestic_re_2022_2024` | 0.0 | remaining unamortized domestic R&E capitalized in 2022-2024 |
| `re_baseline_amortization_this_year` | 0.0 |  |
| `re_catchup_elected` | 'none' | none | one_year | two_year - the Sec. 174A catch-up choice made on the 2025 return |
| `elects_to_amortize_domestic_re` | False |  |
| `qualified_research_expenses` | 0.0 | current-year QREs for the Sec. 41 credit |
| `prior_3yr_qres` | [] | QREs for each of the 3 prior years, oldest first |
| `business_interest_expense` | 0.0 |  |
| `business_interest_income` | 0.0 |  |
| `ebitda` | 0.0 | earnings before interest, taxes, depreciation and amortization (for Sec. 163(j)) |
| `depreciation_amortization` | 0.0 |  |
| `has_retirement_plan` | False |  |
| `nhce_count` | 0 | non-highly compensated employees (plan startup credit) |
| `plan_startup_costs` | 5000.0 |  |
| `planned_employer_contribution_per_employee` | 1000.0 |  |
| `employees_over_credit_wage_cap` | 0 |  |
| `hiring_new_employees` | False |  |
| `childcare_expenses` | 0.0 |  |
| `childcare_referral_expenses` | 0.0 |  |
| `paid_family_leave_wages` | 0.0 |  |
| `qsbs_eligible_stock` | False |  |
| `qsbs_issued_after_jul4_2025` | True | true if the stock was issued after July 4, 2025 (new tiered rules) |
| `qsbs_basis` | 0.0 |  |
| `qsbs_expected_gain` | 0.0 |  |
| `qsbs_years_held_at_sale` | 0.0 |  |
| `qsbs_gross_assets_at_issuance` | 0.0 | corporation's aggregate gross assets when the stock was issued |
| `charitable_contributions` | 0.0 |  |
| `nol_carryforward` | 0.0 |  |
| `capital_gain_to_reinvest` | 0.0 |  |
| `gain_realization_date` | '' |  |
| `qof_investment_date` | '' |  |
| `oz_rural_fund` | False |  |
| `energy_projects_in_progress` | False |  |
| `discount_rate` | 0.07 | rate used to present-value timing benefits |
| `method` | 'law' | law (default) or simplified |
| `as_of` | '' | date of the scan (YYYY-MM-DD); drives deadline checks, defaults to today |

`assets` items:

| Field | Default | Meaning |
|---|---|---|
| `description` | **required** | |
| `cost` | **required** | |
| `recovery_class` | **required** | |
| `acquired_after_jan19_2025` | True | |
| `business_use_pct` | 1.0 | |
| `used_in_manufacturing_building` | False | |
