"""Payroll taxes: FICA, self-employment tax, Additional Medicare tax, NIIT."""
from __future__ import annotations

from dataclasses import dataclass

from .params import DEFAULT_YEAR, param


@dataclass
class FICAResult:
    employee_ss: float
    employee_medicare: float
    employer_ss: float
    employer_medicare: float
    additional_medicare: float  # employee only; an income tax, not deductible by employer

    @property
    def employee_total(self) -> float:
        return round(self.employee_ss + self.employee_medicare, 2)

    @property
    def employer_total(self) -> float:
        return round(self.employer_ss + self.employer_medicare, 2)


def fica(wages: float, status: str = "S", year: int = DEFAULT_YEAR, other_wages_same_return: float = 0.0) -> FICAResult:
    """FICA on W-2 wages for one employee.

    The Additional Medicare tax threshold is applied to combined wages on the
    return (``wages + other_wages_same_return``, e.g. a spouse's wages).
    """
    base = param("ss_wage_base", year)
    ss = min(wages, base) * param("ss_rate", year)
    med = wages * param("medicare_rate", year)
    thr = param("addl_medicare_threshold", year, status)
    combined = wages + other_wages_same_return
    addl = max(0.0, combined - thr) * param("addl_medicare_rate", year)
    return FICAResult(round(ss, 2), round(med, 2), round(ss, 2), round(med, 2), round(addl, 2))


@dataclass
class SEResult:
    net_earnings: float          # SE income x 92.35%
    social_security: float
    medicare: float
    se_tax: float
    deduction_half: float        # above-the-line deduction for 1/2 of SE tax
    additional_medicare: float   # 0.9% on SE earnings above threshold (less wages)


def self_employment_tax(
    se_income: float, status: str = "S", year: int = DEFAULT_YEAR, w2_wages: float = 0.0,
    medicare_wages_on_return: float | None = None,
) -> SEResult:
    """Schedule SE for one person.

    ``w2_wages`` are *this person's* Social Security wages; they use up the wage base.
    ``medicare_wages_on_return`` are all Medicare wages on the return (both spouses on a joint
    return), which reduce the Additional Medicare threshold on Form 8959. Defaults to ``w2_wages``.
    """
    nese = max(0.0, se_income) * param("se_factor", year)
    if nese < 400:
        nese = 0.0
    base_left = max(0.0, param("ss_wage_base", year) - w2_wages)
    ss = min(nese, base_left) * param("ss_rate", year) * 2
    med = nese * param("medicare_rate", year) * 2
    se = ss + med
    mw = w2_wages if medicare_wages_on_return is None else medicare_wages_on_return
    thr_left = max(0.0, param("addl_medicare_threshold", year, status) - mw)
    addl = max(0.0, nese - thr_left) * param("addl_medicare_rate", year)
    return SEResult(round(nese, 2), round(ss, 2), round(med, 2), round(se, 2), round(se / 2, 2), round(addl, 2))


def niit(net_investment_income: float, magi: float, status: str = "S", year: int = DEFAULT_YEAR) -> float:
    """Net investment income tax: 3.8% x lesser of NII or MAGI over threshold."""
    over = max(0.0, magi - param("niit_threshold", year, status))
    return round(min(max(0.0, net_investment_income), over) * param("niit_rate", year), 2)
