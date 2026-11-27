"""Individual-level rules: standard deduction, dependents, OBBBA deductions,
credits, kiddie tax, Social Security inclusion, QBI."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .params import DEFAULT_YEAR, param
from .rates import ordinary_tax


# --------------------------------------------------------------------------
# Standard deduction
# --------------------------------------------------------------------------
def standard_deduction(
    status: str,
    year: int = DEFAULT_YEAR,
    age65_or_blind_boxes: int = 0,
    is_dependent: bool = False,
    earned_income: float = 0.0,
    spouse_itemizes_mfs: bool = False,
) -> float:
    """Standard deduction.

    ``age65_or_blind_boxes`` counts each box checked (taxpayer 65+, taxpayer
    blind, spouse 65+, spouse blind). A dependent's basic deduction is the
    greater of $1,350 or earned income + $450, capped at the normal amount.
    """
    if status == "MFS" and spouse_itemizes_mfs:
        return 0.0
    basic = param("std_deduction", year, status)
    if is_dependent:
        basic = min(basic, max(param("dep_std_min", year), earned_income + param("dep_std_earned_addon", year)))
    return basic + age65_or_blind_boxes * param("std_additional", year, status)


def _phase(amount: float, magi: float, start: float, per_1000: float) -> float:
    """Reduce ``amount`` by ``per_1000`` for each $1,000 (or part) of MAGI over ``start``."""
    if magi <= start:
        return amount
    return max(0.0, amount - math.ceil((magi - start) / 1000.0) * per_1000)


def senior_deduction(num_seniors: int, magi: float, status: str, year: int = DEFAULT_YEAR) -> float:
    """OBBBA $6,000 deduction per individual age 65+, phased out at 6%."""
    if status == "MFS" or num_seniors <= 0:
        return 0.0
    over = max(0.0, magi - param("senior_phaseout_start", year, status))
    # Schedule 1-A: the phase-down applies to EACH qualifying individual's $6,000.
    each = max(0.0, param("senior_deduction", year) - over * param("senior_phaseout_rate", year))
    return round(num_seniors * each, 2)


def tips_deduction(qualified_tips: float, magi: float, status: str, year: int = DEFAULT_YEAR) -> float:
    """No tax on tips: up to $25,000, reduced $100 per $1,000 over $150K/$300K."""
    if status == "MFS":
        return 0.0
    cap = min(qualified_tips, param("tips_max", year))
    return _phase(cap, magi, param("tips_ot_phaseout_start", year, status), param("tips_ot_phaseout_per_1000", year))


def overtime_deduction(qualified_overtime: float, magi: float, status: str, year: int = DEFAULT_YEAR) -> float:
    """No tax on overtime premium: $12,500 / $25,000 MFJ."""
    if status == "MFS":
        return 0.0
    cap = min(qualified_overtime, param("overtime_max", year, status))
    return _phase(cap, magi, param("tips_ot_phaseout_start", year, status), param("tips_ot_phaseout_per_1000", year))


def car_loan_interest_deduction(interest: float, magi: float, status: str, year: int = DEFAULT_YEAR) -> float:
    """Qualified passenger vehicle loan interest: up to $10,000."""
    cap = min(interest, param("car_interest_max", year))
    return _phase(cap, magi, param("car_interest_phaseout_start", year, status),
                  param("car_interest_phaseout_per_1000", year))


# --------------------------------------------------------------------------
# Credits
# --------------------------------------------------------------------------
@dataclass
class ChildCreditResult:
    tentative: float
    after_phaseout: float
    nonrefundable_used: float
    refundable_actc: float


def child_tax_credit(
    qualifying_children: int,
    other_dependents: int,
    magi: float,
    status: str,
    tax_before_credits: float,
    earned_income: float,
    year: int = DEFAULT_YEAR,
    payroll_taxes_paid: float = 0.0,
    eitc: float = 0.0,
) -> ChildCreditResult:
    """CTC ($2,200) + ODC ($500), phase-out $50 per $1,000 over $200K/$400K;
    refundable ACTC = lesser of $1,700/child, unused credit, or 15% x (earned - $2,500).
    With 3+ qualifying children, Schedule 8812 Part II-B lets the 15% amount be replaced by the
    larger of it or (employee Social Security and Medicare taxes + 1/2 SE tax - EITC)."""
    ctc = qualifying_children * param("ctc_per_child", year)
    odc = other_dependents * param("odc_per_dependent", year)
    tentative = ctc + odc
    allowed = _phase(tentative, magi, param("ctc_phaseout_start", year, status), 50)
    nonref = min(allowed, max(0.0, tax_before_credits))
    # Form 8812 Part II-A: unused credit, capped at $1,700/child and 15% of earned income over $2,500.
    earned_amt = max(0.0, 0.15 * (earned_income - 2_500))
    if qualifying_children >= 3:
        earned_amt = max(earned_amt, max(0.0, payroll_taxes_paid - eitc))
    actc = min(allowed - nonref, qualifying_children * param("ctc_refundable", year), earned_amt)
    return ChildCreditResult(tentative, allowed, round(nonref, 2), round(actc, 2))


# --------------------------------------------------------------------------
# Kiddie tax
# --------------------------------------------------------------------------
@dataclass
class KiddieTaxResult:
    child_std_deduction: float
    child_taxable_income: float
    net_unearned_income: float
    tax_at_parent_rate: float
    tax_on_rest_at_child_rate: float
    total_child_tax: float
    tax_if_not_subject: float


def kiddie_tax(
    earned_income: float,
    unearned_income: float,
    parent_taxable_income: float,
    parent_status: str,
    year: int = DEFAULT_YEAR,
) -> KiddieTaxResult:
    """Form 8615 simplified (one child, no preferential income, no itemizing).

    NUI = unearned income - $2,700 (limited to the child's taxable income) is
    taxed as the increase in the parent's tax; the rest at the child's rates.
    """
    std = standard_deduction("S", year, is_dependent=True, earned_income=earned_income)
    ti = max(0.0, earned_income + unearned_income - std)
    nui = min(ti, max(0.0, unearned_income - param("kiddie_threshold", year)))
    parent_increase = ordinary_tax(parent_taxable_income + nui, parent_status, year) - ordinary_tax(
        parent_taxable_income, parent_status, year)
    rest = ordinary_tax(ti - nui, "S", year)
    return KiddieTaxResult(std, ti, nui, round(parent_increase, 2), rest, round(parent_increase + rest, 2),
                           ordinary_tax(ti, "S", year))


# --------------------------------------------------------------------------
# Social Security benefits
# --------------------------------------------------------------------------
@dataclass
class SocialSecurityResult:
    provisional_income: float
    taxable_benefits: float
    tier: str


def taxable_social_security(
    benefits: float, magi_without_ss: float, tax_exempt_interest: float, status: str
) -> SocialSecurityResult:
    """IRC 86 two-tier inclusion. MFS living with spouse: base amounts are 0."""
    base1, base2 = {"MFJ": (32_000, 44_000), "MFS": (0, 0)}.get(status, (25_000, 34_000))
    pi = magi_without_ss + tax_exempt_interest + 0.5 * benefits
    if pi <= base1:
        return SocialSecurityResult(pi, 0.0, "none")
    if pi <= base2:
        return SocialSecurityResult(pi, round(min(0.5 * (pi - base1), 0.5 * benefits), 2), "50%")
    tier1 = min(0.5 * benefits, 0.5 * (base2 - base1))
    amt = min(0.85 * (pi - base2) + tier1, 0.85 * benefits)
    return SocialSecurityResult(pi, round(amt, 2), "85%")


# --------------------------------------------------------------------------
# QBI (Sec. 199A)
# --------------------------------------------------------------------------
@dataclass
class QBIResult:
    deduction: float
    above_threshold: bool
    note: str


def qbi_deduction(
    qbi: float,
    taxable_income_before_qbi: float,
    net_capital_gain: float,
    status: str,
    year: int = DEFAULT_YEAR,
    active: bool = True,
) -> QBIResult:
    """Lesser of 20% x QBI or 20% x (TI before QBI - net capital gain incl. QD), plus the 2026+
    $400 minimum for at least $1,000 of active QBI. Simplified: assumes the W-2 wage / UBIA and SSTB
    limits don't bind - above the threshold use :func:`qbi_deduction_full`.

    QBI should already be net of losses from other businesses and reduced by the deductible half of
    SE tax, SE health insurance and SE retirement contributions. Negative QBI gives no deduction and
    carries forward."""
    rate = param("qbi_rate", year)
    if qbi <= 0:
        return QBIResult(0.0, False, "Net QBI is a loss: no deduction; the loss carries forward." if qbi < 0 else "")
    ded = max(0.0, min(rate * qbi, rate * max(0.0, taxable_income_before_qbi - net_capital_gain)))
    min_ded = param("qbi_min_deduction", year)
    if min_ded and active and qbi >= param("qbi_min_qbi", year):
        ded = max(ded, min_ded)
    above = taxable_income_before_qbi > param("qbi_threshold", year, status)
    note = ("Above the QBI threshold: the W-2 wage / UBIA / SSTB limits may reduce this - pass "
            "qbi_w2_wages / qbi_ubia / qbi_sstb for the full computation." if above else "")
    return QBIResult(round(ded, 2), above, note)


@dataclass
class QBIDetail:
    qbi: float
    tentative: float
    wage_limit: float
    phase_in_pct: float
    sstb_applicable_pct: float
    income_limit: float
    deduction: float
    note: str = ""


def qbi_deduction_full(qbi: float, w2_wages: float, ubia: float, taxable_income_before_qbi: float,
                       net_capital_gain: float, status: str, sstb: bool = False,
                       year: int = DEFAULT_YEAR, active_participant: bool = True) -> QBIDetail:
    """Sec. 199A for one trade or business: 20% of QBI, limited above the threshold by the
    greater of 50% of W-2 wages or 25% of W-2 wages + 2.5% of UBIA, with SSTB phase-out,
    the overall 20%-of-(TI - net capital gain) cap and the 2026+ $400 minimum."""
    thr = param("qbi_threshold", year, status)
    rng = param("qbi_phase_range", year, status)
    ti = max(0.0, taxable_income_before_qbi)
    over = max(0.0, ti - thr)
    phase = min(1.0, over / rng) if rng else 1.0
    app = 1.0
    if sstb:
        app = max(0.0, 1.0 - phase)
    q, w, u = qbi * app, w2_wages * app, ubia * app
    tentative = 0.20 * max(0.0, q)
    wage_limit = max(0.5 * w, 0.25 * w + 0.025 * u)
    if over <= 0:
        ded = tentative
    elif phase >= 1.0:
        ded = min(tentative, wage_limit)
    else:
        ded = tentative - max(0.0, tentative - wage_limit) * phase
    income_limit = 0.20 * max(0.0, ti - net_capital_gain)
    ded = max(0.0, min(ded, income_limit))
    note = ""
    min_ded = param("qbi_min_deduction", year)
    # The minimum applies to QBI from *qualified* trades or businesses, so a fully phased-out SSTB doesn't count.
    if min_ded and active_participant and q >= param("qbi_min_qbi", year):
        if ded < min_ded:
            note = "2026+ minimum deduction applied."
        ded = max(ded, min_ded)
    if qbi < 0:
        ded, note = 0.0, "Negative QBI carries forward and reduces next year's QBI."
    return QBIDetail(qbi, round(tentative, 2), round(wage_limit, 2), phase, app, round(income_limit, 2),
                     round(ded, 2), note)
