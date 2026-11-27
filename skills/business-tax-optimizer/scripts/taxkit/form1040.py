"""End-to-end Form 1040 computation following the individual tax formula:

    Gross income - for-AGI deductions = AGI
    AGI - (standard or itemized) - Schedule 1-A deductions - QBI = taxable income
    tax (with preferential rates) + other taxes - credits - payments = due / (refund)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from . import individual as ind
from .itemized import ItemizedResult, itemized_deductions, section_68_reduction
from .params import DEFAULT_YEAR, param
from .payroll import niit, self_employment_tax
from .rates import income_tax


@dataclass
class Return1040:
    year: int = DEFAULT_YEAR
    status: str = "S"
    method: str = "law"                    # "simplified" = 'pick smaller' capital gain shortcut
    # Income
    wages: float = 0.0
    taxable_interest: float = 0.0
    ordinary_dividends: float = 0.0        # includes qualified dividends
    qualified_dividends: float = 0.0
    net_capital_gain: float = 0.0          # Schedule D net (negative = loss, already limited to -3,000)
    net_ltcg_for_rates: float = 0.0        # portion eligible for 0/15/20 (smaller of net LT and net gain)
    schedule_c_profit: float = 0.0
    se_person_wages: float | None = None   # Social Security wages of the self-employed person (None: = wages,
                                           # except MFJ where it defaults to 0 - i.e. the other spouse has the W-2)
    other_income: float = 0.0              # alimony (pre-2019), unemployment, prizes, gambling, K-1 etc.
    taxable_social_security: float = 0.0
    # Adjustments (for AGI)
    se_health_insurance: float = 0.0
    se_retirement: float = 0.0
    ira_deduction: float = 0.0
    student_loan_interest: float = 0.0
    educator_expenses: float = 0.0
    alimony_paid: float = 0.0
    other_adjustments: float = 0.0
    # Deductions
    itemized: Dict[str, float] = field(default_factory=dict)   # kwargs for itemized_deductions
    age65_or_blind_boxes: int = 0
    num_seniors: int = 0
    qualified_tips: float = 0.0
    qualified_overtime: float = 0.0
    car_loan_interest: float = 0.0
    other_qbi: float = 0.0                 # QBI from K-1s etc. (may be negative); Sch C QBI is computed automatically
    qbi_override: float | None = None      # use this QBI deduction (e.g. a full Sec. 199A computation)
    qbi_w2_wages: float | None = None      # set (with qbi_ubia / qbi_sstb) to apply the wage/UBIA/SSTB limits
    qbi_ubia: float = 0.0
    qbi_sstb: bool = False
    qbi_active: bool = True                # materially participates (2026+ $400 minimum)
    # Credits / payments / other taxes
    qualifying_children: int = 0
    other_dependents: int = 0
    other_credits: float = 0.0
    eitc: float = 0.0                      # EITC claimed (not computed; reduces the 3+ child ACTC alternative)
    net_investment_income: float = 0.0
    withholding: float = 0.0
    estimated_payments: float = 0.0


@dataclass
class Result1040:
    gross_income: float
    adjustments: float
    agi: float
    standard_deduction: float
    itemized: ItemizedResult
    deduction_used: str
    deduction_amount: float
    schedule_1a: float
    qbi_deduction: float
    taxable_income: float
    income_tax: float
    se_tax: float
    additional_medicare: float
    niit: float
    total_tax_before_credits: float
    nonrefundable_credits: float
    refundable_credits: float
    total_tax: float
    payments: float
    balance_due: float                       # negative = refund
    marginal_rate: float
    effective_rate: float
    lines: List[tuple] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def compute_return(r: Return1040) -> Result1040:
    y, s = r.year, r.status
    warnings: List[str] = []
    se_w2 = r.se_person_wages if r.se_person_wages is not None else (0.0 if s == "MFJ" else r.wages)
    se = self_employment_tax(r.schedule_c_profit, s, y, w2_wages=se_w2, medicare_wages_on_return=r.wages)
    gross = (r.wages + r.taxable_interest + r.ordinary_dividends + r.net_capital_gain + r.schedule_c_profit
             + r.other_income + r.taxable_social_security)
    other_adj = (se.deduction_half + r.se_health_insurance + r.se_retirement + r.ira_deduction
                 + min(r.educator_expenses, 300) + r.alimony_paid + r.other_adjustments)
    # Student loan interest (IRC 221): phased out on MAGI figured before this deduction; not allowed MFS.
    sli = min(r.student_loan_interest, param("sli_max", y))
    if sli and s == "MFS":
        sli = 0.0
    elif sli:
        over = max(0.0, (gross - other_adj) - param("sli_phase_start", y, s))
        sli = round(max(0.0, sli * (1 - over / param("sli_phase_range", y, s))), 2)
    adj = other_adj + sli
    agi = gross - adj
    std = ind.standard_deduction(s, y, r.age65_or_blind_boxes)
    item = itemized_deductions(agi, s, y, **r.itemized)
    sch1a_base = (ind.senior_deduction(r.num_seniors, agi, s, y) + ind.tips_deduction(r.qualified_tips, agi, s, y)
                  + ind.overtime_deduction(r.qualified_overtime, agi, s, y)
                  + ind.car_loan_interest_deduction(r.car_loan_interest, agi, s, y))
    sec68 = section_68_reduction(item.total, agi - sch1a_base, s, y)
    item_allowed = item.total - sec68
    use_item = item_allowed > std
    ded = item_allowed if use_item else std
    sch1a = sch1a_base
    if not use_item:
        sch1a += min(r.itemized.get("charity_cash_public", 0.0), param("nonitemizer_charity", y, s))
    elif sec68:
        warnings.append(f"Sec. 68 (2/37) reduced itemized deductions by {sec68:,.2f}.")
    ti_before_qbi = max(0.0, agi - ded - sch1a)
    # QBI stays signed: a Schedule C loss offsets other QBI (net loss carries forward).
    qbi_amt = r.schedule_c_profit - se.deduction_half - r.se_health_insurance - r.se_retirement + r.other_qbi
    if r.schedule_c_profit <= 0:
        qbi_amt = r.schedule_c_profit + r.other_qbi
    pref = r.qualified_dividends + max(0.0, r.net_ltcg_for_rates)
    if r.qbi_override is not None:
        qbi = min(r.qbi_override, ti_before_qbi)
    elif r.qbi_w2_wages is not None:
        qbi = ind.qbi_deduction_full(qbi_amt, r.qbi_w2_wages, r.qbi_ubia, ti_before_qbi, pref, s, r.qbi_sstb, y,
                                     r.qbi_active).deduction
    else:
        q = ind.qbi_deduction(qbi_amt, ti_before_qbi, pref, s, y, r.qbi_active)
        qbi = q.deduction
        if q.note and qbi_amt > 0:
            warnings.append(q.note)
    ti = max(0.0, ti_before_qbi - qbi)
    tax = income_tax(ti, s, y, r.qualified_dividends, r.net_ltcg_for_rates, method=r.method)
    addl_med = se.additional_medicare + max(0.0, r.wages - param("addl_medicare_threshold", y, s)) * param(
        "addl_medicare_rate", y)
    n = niit(r.net_investment_income, agi, s, y)
    before = tax.tax + se.se_tax + addl_med + n
    base = param("ss_wage_base", y)
    payroll_paid = (param("ss_rate", y) * min(r.wages, base) + param("medicare_rate", y) * r.wages
                    + max(0.0, r.wages - param("addl_medicare_threshold", y, s)) * param("addl_medicare_rate", y)
                    + se.deduction_half)
    ctc = ind.child_tax_credit(r.qualifying_children, r.other_dependents, agi, s, tax.tax,
                               r.wages + r.schedule_c_profit - se.deduction_half, y,
                               payroll_taxes_paid=payroll_paid, eitc=r.eitc)
    nonref = min(tax.tax, ctc.nonrefundable_used + r.other_credits)
    total = before - nonref
    pay = r.withholding + r.estimated_payments + ctc.refundable_actc
    res = Result1040(
        gross_income=round(gross, 2), adjustments=round(adj, 2), agi=round(agi, 2), standard_deduction=std,
        itemized=item, deduction_used="itemized" if use_item else "standard", deduction_amount=round(ded, 2),
        schedule_1a=round(sch1a, 2), qbi_deduction=qbi, taxable_income=round(ti, 2), income_tax=tax.tax,
        se_tax=se.se_tax, additional_medicare=round(addl_med, 2), niit=n,
        total_tax_before_credits=round(before, 2), nonrefundable_credits=round(nonref, 2),
        refundable_credits=ctc.refundable_actc, total_tax=round(total, 2),
        payments=round(pay, 2), balance_due=round(total - pay, 2),
        marginal_rate=tax.marginal_rate, effective_rate=(total / agi) if agi > 0 else 0.0,
        warnings=warnings,
    )
    res.lines = [
        ("Gross income", res.gross_income), ("Adjustments to income", res.adjustments), ("AGI", res.agi),
        (f"Deduction ({res.deduction_used})", res.deduction_amount), ("Schedule 1-A deductions", res.schedule_1a),
        ("QBI deduction", res.qbi_deduction), ("Taxable income", res.taxable_income),
        ("Income tax", res.income_tax), ("Self-employment tax", res.se_tax),
        ("Additional Medicare tax", res.additional_medicare), ("Net investment income tax", res.niit),
        ("Nonrefundable credits", -res.nonrefundable_credits), ("Total tax", res.total_tax),
        ("Payments + refundable credits", -res.payments), ("Balance due / (refund)", res.balance_due),
    ]
    return res
