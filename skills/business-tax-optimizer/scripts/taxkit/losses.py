"""Losses and limited deductions: casualty, EBL, NOL, vacation homes, hobbies."""
from __future__ import annotations

from dataclasses import dataclass

from .params import DEFAULT_YEAR, param


@dataclass
class CasualtyResult:
    loss_before_limits: float
    after_per_event: float
    agi_floor: float
    deductible: float


def casualty_loss(adjusted_basis: float, fmv_before: float, fmv_after: float, insurance: float,
                  agi: float, personal: bool = True, completely_destroyed_business: bool = False,
                  qualified_disaster: bool = False, year: int = DEFAULT_YEAR) -> CasualtyResult:
    """Casualty loss.

    * Business property completely destroyed: loss = adjusted basis - insurance.
    * Otherwise: lesser of adjusted basis or decline in FMV, minus insurance.
    * Personal: only in a federally (2026+: or qualifying state) declared disaster;
      reduce by $100 per event and then 10% of AGI. Qualified disaster losses:
      $500 per event and no 10% floor.
    """
    decline = fmv_before - fmv_after
    if not personal and completely_destroyed_business:
        base = adjusted_basis
    else:
        base = min(adjusted_basis, decline)
    loss = max(0.0, base - insurance)
    if not personal:
        return CasualtyResult(round(loss, 2), round(loss, 2), 0.0, round(loss, 2))
    per_event = 500 if qualified_disaster else param("casualty_per_event", year)
    after = max(0.0, loss - per_event)
    floor = 0.0 if qualified_disaster else param("casualty_agi_pct", year) * agi
    return CasualtyResult(round(loss, 2), round(after, 2), round(floor, 2), round(max(0.0, after - floor), 2))


@dataclass
class EBLResult:
    net_business_loss: float
    threshold: float
    allowed: float
    disallowed_to_nol: float


def excess_business_loss(business_income: float, business_deductions: float, status: str,
                         year: int = DEFAULT_YEAR) -> EBLResult:
    """IRC 461(l): business losses above the threshold become an NOL carryforward."""
    loss = max(0.0, business_deductions - business_income)
    thr = param("ebl_threshold", year, status)
    allowed = min(loss, thr)
    return EBLResult(loss, thr, allowed, loss - allowed)


@dataclass
class NOLResult:
    taxable_income_before_nol: float
    nol_deduction: float
    taxable_income: float
    nol_carryforward_remaining: float


def apply_nol(taxable_income_before_nol: float, nol_carryforward: float, year: int = DEFAULT_YEAR) -> NOLResult:
    """Post-2017 NOLs: deduction limited to 80% of taxable income before the NOL."""
    ded = min(nol_carryforward, param("nol_pct_limit", year) * max(0.0, taxable_income_before_nol))
    return NOLResult(taxable_income_before_nol, round(ded, 2), round(taxable_income_before_nol - ded, 2),
                     round(nol_carryforward - ded, 2))


def compute_nol(taxable_income: float, net_capital_gain_included: float, std_or_itemized_deduction: float,
                nonbusiness_income: float, nonbusiness_deductions_other: float = 0.0) -> float:
    """Individual NOL: start with (negative)
    taxable income, remove net capital gains, add back the standard/itemized
    deduction, remove non-business income. Returns the NOL as a positive number."""
    adj = (taxable_income - net_capital_gain_included + std_or_itemized_deduction
           - nonbusiness_income + nonbusiness_deductions_other)
    return round(max(0.0, -adj), 2)


@dataclass
class VacationHomeResult:
    classification: str
    rental_pct_for_operating: float
    rental_pct_for_interest_taxes: float
    gross_rent: float
    direct_expenses: float
    interest_taxes_rental: float
    operating_rental: float
    depreciation_rental: float
    net_rental_income: float
    interest_taxes_to_schedule_a: float
    note: str


def vacation_home(rental_days: int, personal_days: int, gross_rent: float, mortgage_interest: float,
                  property_taxes: float, operating_expenses: float, depreciation: float,
                  direct_rental_expenses: float = 0.0, method: str = "tax_court") -> VacationHomeResult:
    """IRC 280A.

    * Rented < 15 days: rent is excluded, no rental deductions.
    * Personal use <= greater of 14 days or 10% of rental days: rental property,
      expenses allocated by rental / total use days, loss allowed (subject to passive rules).
    * Otherwise: personal residence ("dual use"): expenses limited to rent, in the
      order direct expenses -> interest & taxes -> operating -> depreciation.
      ``method='tax_court'`` (Bolton) allocates interest/taxes by rental days / 365;
      ``method='irs'`` uses rental / total use days for everything.
    """
    it = mortgage_interest + property_taxes
    total_use = rental_days + personal_days
    if rental_days < 15:
        return VacationHomeResult("minimal rental (<15 days)", 0, 0, gross_rent, 0, 0, 0, 0, 0, it,
                                  "Rental income excluded; interest/taxes are itemized deductions.")
    op_pct = rental_days / total_use
    limit = max(14, 0.10 * rental_days)
    if personal_days <= limit:
        it_r = it * op_pct
        op_r = operating_expenses * op_pct
        dep_r = depreciation * op_pct
        net = gross_rent - direct_rental_expenses - it_r - op_r - dep_r
        return VacationHomeResult("primarily rental", op_pct, op_pct, gross_rent, direct_rental_expenses,
                                  round(it_r, 2), round(op_r, 2), round(dep_r, 2), round(net, 2),
                                  round(it - it_r, 2), "Loss allowed (subject to passive activity rules).")
    it_pct = rental_days / 365 if method == "tax_court" else op_pct
    remaining = gross_rent - direct_rental_expenses
    it_r = it * it_pct
    it_used = min(it_r, max(0.0, remaining))   # any excess stays on Schedule A
    remaining -= it_used
    op_r = min(operating_expenses * op_pct, max(0.0, remaining))
    remaining -= op_r
    dep_r = min(depreciation * op_pct, max(0.0, remaining))
    remaining -= dep_r
    return VacationHomeResult("dual use (personal residence)", op_pct, it_pct, gross_rent,
                              direct_rental_expenses, round(it_used, 2), round(op_r, 2), round(dep_r, 2),
                              round(remaining, 2), round(it - it_used, 2),
                              "Expenses limited to rental income; no loss allowed.")


def hobby_income(gross_receipts: float, cost_of_goods_sold: float = 0.0) -> float:
    """Hobby: report gross income (receipts - COGS); other hobby expenses are
    permanently non-deductible miscellaneous itemized deductions."""
    return round(gross_receipts - cost_of_goods_sold, 2)


def presumed_for_profit(profit_years_in_last_5: int) -> bool:
    """IRC 183(d): presumed profit-seeking if profitable in 3 of the last 5 years."""
    return profit_years_in_last_5 >= 3
