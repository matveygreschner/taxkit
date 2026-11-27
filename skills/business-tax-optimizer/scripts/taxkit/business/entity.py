"""Entity-choice and owner-compensation modeling.

Computes the *combined* federal tax (entity + owner, including both halves of
payroll tax) on the same pre-tax business profit under each entity type, using
the individual engine for the owner's Form 1040 and a full Sec. 199A
computation (wage limit, SSTB phase-out, 2026 $400 minimum).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..form1040 import Return1040, compute_return
from ..params import DEFAULT_YEAR, param
from ..payroll import fica


from ..individual import QBIDetail, qbi_deduction_full  # noqa: E402,F401  (re-exported)


# ----------------------------------------------------------- entity model ---
@dataclass
class EntityResult:
    entity: str
    owner_wages: float
    employer_payroll_tax: float
    entity_income_tax: float
    entity_state_tax: float
    owner_federal_tax: float          # Form 1040 total tax (income + SE + Addl Medicare + NIIT)
    owner_payroll_withheld: float     # employee FICA on owner wages
    owner_state_tax: float
    qbi_deduction: float
    distributed: float
    retained_in_entity: float
    total_tax: float
    after_tax_cash_to_owner: float
    effective_rate: float
    lines: Dict[str, float] = field(default_factory=dict)


def _owner_return(year, status, method, wages, se_income, other_ord, qual_div, nii, other_income,
                  qbi_amount, business_w2, ubia, sstb, extra):
    base = dict(year=year, status=status, method=method, wages=wages, schedule_c_profit=se_income,
                other_income=other_ord + other_income, ordinary_dividends=qual_div, qualified_dividends=qual_div,
                net_investment_income=nii, **extra)
    first = compute_return(Return1040(**base))
    ti_before_qbi = first.taxable_income + first.qbi_deduction
    detail = qbi_deduction_full(qbi_amount, business_w2, ubia, ti_before_qbi, qual_div, status, sstb, year) \
        if qbi_amount else None
    ded = detail.deduction if detail else 0.0
    r = compute_return(Return1040(**base, qbi_override=ded))
    return r, ded


def compare_entities(profit_before_owner_pay: float, owner_salary: float = 0.0, status: str = "MFJ",
                     year: int = DEFAULT_YEAR, other_income: float = 0.0, other_employee_wages: float = 0.0,
                     ubia: float = 0.0, sstb: bool = False, state_rate: float = 0.0,
                     state_corp_rate: Optional[float] = None, c_corp_distribution_pct: float = 1.0,
                     method: str = "law", entities: Optional[List[str]] = None,
                     extra_1040: Optional[dict] = None) -> List[EntityResult]:
    """Combined tax on the same pre-tax profit under each entity type (one owner).

    ``profit_before_owner_pay`` is profit after all expenses except owner pay and
    employer payroll tax on owner pay. ``owner_salary`` is the reasonable salary
    paid as W-2 wages in an S or C corporation (ignored for sole prop/partnership,
    whose owners can't be employees). ``state_rate`` is a flat illustrative
    state income tax rate. C corp profits are distributed as qualified dividends
    in the proportion ``c_corp_distribution_pct``.
    """
    entities = entities or ["sole_prop", "s_corp", "c_corp"]
    extra = dict(extra_1040 or {})
    reserved = {"year", "status", "method", "wages", "schedule_c_profit", "other_income", "ordinary_dividends",
                "qualified_dividends", "net_investment_income", "qbi_override"}
    clash = sorted(reserved & set(extra))
    if clash:
        raise ValueError(f"extra_1040 can't set {', '.join(clash)} - use other_income / the function arguments instead")
    scr = state_rate if state_corp_rate is None else state_corp_rate
    out = []
    for e in entities:
        if e in ("sole_prop", "partnership"):
            wages, er_fica, ee_fica = 0.0, 0.0, 0.0
            r, qbi = _owner_return(year, status, method, 0.0, profit_before_owner_pay, 0.0, 0.0, 0.0,
                                   other_income, profit_before_owner_pay - 0.0, other_employee_wages, ubia,
                                   sstb, extra)
            # QBI is reduced by the deductible half of SE tax.
            if qbi:
                r, qbi = _owner_return(year, status, method, 0.0, profit_before_owner_pay, 0.0, 0.0, 0.0,
                                       other_income, profit_before_owner_pay - r.se_tax / 2,
                                       other_employee_wages, ubia, sstb, extra)
            owner_state = state_rate * max(0.0, r.agi)
            total = r.total_tax + owner_state
            cash = profit_before_owner_pay - total + other_income
            out.append(EntityResult(e, 0.0, 0.0, 0.0, 0.0, r.total_tax, 0.0, round(owner_state, 2), qbi,
                                    profit_before_owner_pay, 0.0, round(total, 2), round(cash, 2),
                                    total / profit_before_owner_pay if profit_before_owner_pay else 0.0,
                                    {"se_tax": r.se_tax, "income_tax": r.income_tax, "agi": r.agi,
                                     "taxable_income": r.taxable_income}))
            continue
        # The salary is actually paid even in a weak year; any shortfall becomes an entity loss
        # (S corp: flows through, subject to basis / at-risk / passive / Sec. 461(l); C corp: NOL).
        wages = max(0.0, owner_salary)
        f = fica(wages, status, year)
        er_fica, ee_fica = f.employer_total, f.employee_total
        entity_profit = profit_before_owner_pay - wages - er_fica
        if e == "s_corp":
            r, qbi = _owner_return(year, status, method, wages, 0.0, entity_profit, 0.0, 0.0, other_income,
                                   entity_profit, wages + other_employee_wages, ubia, sstb, extra)
            owner_state = state_rate * max(0.0, r.agi)
            total = er_fica + ee_fica + r.total_tax + owner_state
            cash = profit_before_owner_pay - total + other_income
            out.append(EntityResult(e, wages, er_fica, 0.0, 0.0, r.total_tax, ee_fica, round(owner_state, 2), qbi,
                                    entity_profit, 0.0, round(total, 2), round(cash, 2),
                                    total / profit_before_owner_pay if profit_before_owner_pay else 0.0,
                                    {"k1_income": round(entity_profit, 2), "income_tax": r.income_tax,
                                     "additional_medicare": r.additional_medicare}))
        elif e == "c_corp":
            corp_state = scr * max(0.0, entity_profit)   # loss years: no tax, NOL carries forward
            corp_tax = param("corp_rate", year) * max(0.0, entity_profit - corp_state)
            after = entity_profit - corp_tax - corp_state
            div = max(0.0, after) * c_corp_distribution_pct
            r, _ = _owner_return(year, status, method, wages, 0.0, 0.0, div, div, other_income, 0.0, 0.0, 0.0,
                                 False, extra)
            owner_state = state_rate * max(0.0, r.agi)
            total = er_fica + ee_fica + corp_tax + corp_state + r.total_tax + owner_state
            cash = wages - ee_fica + div - r.total_tax - owner_state + other_income
            out.append(EntityResult(e, wages, er_fica, round(corp_tax, 2), round(corp_state, 2), r.total_tax,
                                    ee_fica, round(owner_state, 2), 0.0, round(div, 2), round(after - div, 2),
                                    round(total, 2), round(cash, 2),
                                    total / profit_before_owner_pay if profit_before_owner_pay else 0.0,
                                    {"corp_taxable_income": round(entity_profit, 2), "dividend": round(div, 2),
                                     "niit": r.niit}))
        else:
            raise ValueError(f"unknown entity {e!r}")
    return out


def reasonable_comp_sweep(profit_before_owner_pay: float, status: str = "MFJ", year: int = DEFAULT_YEAR,
                          salary_pcts=(0.3, 0.4, 0.5, 0.6, 0.7), **kw) -> List[dict]:
    """S corp total tax at several salary levels, versus sole proprietorship."""
    base = compare_entities(profit_before_owner_pay, 0.0, status, year, entities=["sole_prop"], **kw)[0]
    rows = []
    for p in salary_pcts:
        s = compare_entities(profit_before_owner_pay, profit_before_owner_pay * p, status, year,
                             entities=["s_corp"], **kw)[0]
        rows.append({"salary_pct": p, "salary": round(profit_before_owner_pay * p, 2), "s_corp_total_tax": s.total_tax,
                     "sole_prop_total_tax": base.total_tax, "savings_vs_sole_prop": round(base.total_tax - s.total_tax, 2)})
    return rows
