"""Gross income inclusions and exclusions."""
from __future__ import annotations

from dataclasses import dataclass

from .params import DEFAULT_YEAR, GTL_TABLE, param


def imputed_interest(loan_amount: float, afr: float, stated_rate: float, loan_type: str = "gift",
                     borrower_nii: float = 0.0, months: float = 12) -> float:
    """Below-market loan rules (IRC 7872).

    * Any loan over $100,000: impute the full foregone interest.
    * Gift (personal) loans <= $10,000: none.
    * Gift loans $10,001-$100,000: none if borrower NII <= $1,000; otherwise
      the lesser of foregone interest or borrower NII.
    * Other (business/compensation) loans <= $10,000: none; otherwise full.
    """
    foregone = max(0.0, loan_amount * (afr - stated_rate) * months / 12)
    if loan_amount > 100_000:
        return round(foregone, 2)
    if loan_amount <= 10_000:
        return 0.0
    if loan_type == "gift":
        if borrower_nii <= 1_000:
            return 0.0
        return round(min(foregone, borrower_nii), 2)
    return round(foregone, 2)


@dataclass
class AnnuityResult:
    expected_return: float
    exclusion_ratio: float
    annual_payment: float
    annual_excluded: float
    annual_taxable: float


def annuity_exclusion(investment: float, monthly_payment: float, expected_return_multiple: float,
                      years_received_so_far: float = 0.0) -> AnnuityResult:
    """Exclusion ratio = investment / expected return; once the investment is
    fully recovered, every payment is taxable.
    ``expected_return_multiple`` comes from Reg. 1.72-9 Table V (e.g. 20.0 at age 65)."""
    annual = monthly_payment * 12
    er = annual * expected_return_multiple
    ratio = min(1.0, investment / er) if er else 0.0
    excl = annual * ratio
    recovered = excl * years_received_so_far
    if recovered >= investment:
        excl = 0.0
    elif recovered + excl > investment:
        excl = investment - recovered
    return AnnuityResult(round(er, 2), ratio, round(annual, 2), round(excl, 2), round(annual - excl, 2))


def group_term_life_income(coverage: float, age: int, employee_paid: float = 0.0,
                           months: int = 12, year: int = DEFAULT_YEAR) -> float:
    """Taxable cost of employer group-term life over $50,000 (Table I)."""
    rate = [r for a, r in GTL_TABLE if age >= a][-1]
    excess = max(0.0, coverage - param("gtl_exclusion", year)) / 1000
    return round(max(0.0, excess * rate * months - employee_paid), 2)


def feie(foreign_earned_income: float, qualifying_days: int, year: int = DEFAULT_YEAR,
         days_in_year: int = 365) -> float:
    """Foreign earned income exclusion, prorated by qualifying days."""
    limit = param("feie_limit", year) * qualifying_days / days_in_year
    return round(min(foreign_earned_income, limit), 2)


def scholarship_taxable(total_received: float, tuition_fees_books: float) -> float:
    """Only qualified tuition/fees/books are excluded; room and board is taxable."""
    return round(max(0.0, total_received - tuition_fees_books), 2)


def ltc_taxable(total_cost: float, days: int, insurance_received: float, medicare_paid: float = 0.0,
                year: int = DEFAULT_YEAR) -> float:
    """Per-diem LTC benefits: excludable = max(per diem limit x days, actual cost)
    - other reimbursements; excess benefits are income."""
    limit = max(param("ltc_per_diem", year) * days, total_cost) - medicare_paid
    return round(max(0.0, insurance_received - limit), 2)


def property_damages_taxable(award: float, basis: float) -> float:
    """Property damages are a return of capital up to basis."""
    return round(max(0.0, award - basis), 2)


def oid_accrual(principal: float, annual_rate: float, years: int) -> list:
    """Annual compounding interest that must be reported each year even though
    it is paid at maturity."""
    rows, bal = [], principal
    for y in range(1, years + 1):
        interest = bal * annual_rate
        bal += interest
        rows.append((y, round(interest, 2), round(bal, 2)))
    return rows


def tax_benefit_refund_income(state_refund: float, itemized_claimed: float, standard_deduction_then: float,
                              itemized_prior_year: bool = True) -> float:
    """State refund is income only to the extent the prior deduction gave a benefit."""
    if not itemized_prior_year:
        return 0.0
    benefit = max(0.0, itemized_claimed - standard_deduction_then)
    return round(min(state_refund, benefit), 2)
