"""Business entities: owner reporting, outside basis roll-forward, C corp tax."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

from .params import DEFAULT_YEAR, param

ENTITY_TYPES = ("sole_prop", "partnership", "s_corp", "c_corp")


@dataclass
class OwnerReporting:
    entity: str
    wages_w2: float = 0.0
    guaranteed_payments: float = 0.0
    business_income: float = 0.0       # Schedule C (sole prop) or K-1 ordinary income/loss
    dividends: float = 0.0
    tax_free_distribution: float = 0.0
    subject_to_fica: float = 0.0
    subject_to_se_tax: float = 0.0
    notes: List[str] = field(default_factory=list)


def owner_reporting(
    entity: str,
    book_net_income: float,
    owner_salary_deducted: float,
    distributions: float = 0.0,
    ownership_pct: float = 1.0,
    general_partner: bool = True,
    has_basis: bool = True,
) -> OwnerReporting:
    """What the owner reports when the business has deducted the owner's "salary"

    * Sole prop / SMLLC: owner pay is not deductible - add it back; all of it is SE income.
    * C corp: salary is W-2 wages (FICA); distributions from E&P are dividends.
    * S corp: salary is W-2 wages (FICA); K-1 share of income/loss; distributions are
      tax-free to the extent of basis.
    * Partnership: owner pay is a guaranteed payment (SE tax); K-1 share of income/loss;
      distributions tax-free to the extent of basis.
    """
    if entity not in ENTITY_TYPES:
        raise ValueError(f"entity must be one of {ENTITY_TYPES}")
    r = OwnerReporting(entity)
    if entity == "sole_prop":
        r.business_income = book_net_income + owner_salary_deducted
        r.subject_to_se_tax = max(0.0, r.business_income)
        r.notes.append("Sole proprietors cannot pay themselves wages; owner draws are not deductible.")
        if distributions:
            r.notes.append("Owner withdrawals are not income or deductions.")
    elif entity == "c_corp":
        r.wages_w2 = owner_salary_deducted
        r.dividends = distributions
        r.subject_to_fica = owner_salary_deducted
        r.notes.append("Corporate loss stays in the corporation (NOL); it does not flow through.")
    elif entity == "s_corp":
        r.wages_w2 = owner_salary_deducted
        r.business_income = book_net_income * ownership_pct
        r.subject_to_fica = owner_salary_deducted
        r.tax_free_distribution = distributions if has_basis else 0.0
        r.notes.append("K-1 ordinary income/loss is not subject to SE tax for S corp shareholders.")
    else:  # partnership
        r.guaranteed_payments = owner_salary_deducted
        r.business_income = book_net_income * ownership_pct
        r.tax_free_distribution = distributions if has_basis else 0.0
        if general_partner:
            r.subject_to_se_tax = r.guaranteed_payments + r.business_income
        else:
            r.subject_to_se_tax = r.guaranteed_payments
            r.notes.append("Limited partner: only guaranteed payments are SE income.")
    return r


@dataclass
class BasisYear:
    year: int
    beginning_basis: float
    contributions: float
    income_share: float
    distributions: float
    tax_free_distribution: float
    taxable_distribution_gain: float
    loss_share: float
    suspended_loss_used: float
    loss_allowed: float
    loss_suspended_cf: float
    ending_basis: float
    net_reported: float  # income share - allowed loss + gain on excess distribution


def basis_rollforward(
    contributions: Sequence[float],
    net_income: Sequence[float],
    distributions: Sequence[float],
    ownership_pct: float = 1.0,
    beginning_basis: float = 0.0,
    shares_are_entity_level: bool = True,
) -> List[BasisYear]:
    """Owner's outside basis in a partnership / S corp, year by year.

    Ordering: + contributions, + income, - distributions (excess over basis = capital gain),
    - losses (limited to basis; excess suspended and carried forward).
    ``net_income`` is entity-level (multiplied by ``ownership_pct``) unless
    ``shares_are_entity_level`` is False. ``distributions`` are to this owner.
    """
    rows: List[BasisYear] = []
    basis = beginning_basis
    suspended = 0.0
    for i, (c, ni, d) in enumerate(zip(contributions, net_income, distributions), start=1):
        share = ni * ownership_pct if shares_are_entity_level else ni
        inc = max(0.0, share)
        loss = max(0.0, -share)
        start = basis
        basis += c + inc
        free = min(d, basis)
        gain = d - free
        basis -= free
        avail_loss = suspended + loss
        allowed = min(avail_loss, basis)
        used_susp = min(suspended, allowed)
        basis -= allowed
        suspended = avail_loss - allowed
        rows.append(BasisYear(i, round(start, 2), c, round(inc, 2), d, round(free, 2), round(gain, 2),
                              round(loss, 2), round(used_susp, 2), round(allowed, 2), round(suspended, 2),
                              round(basis, 2), round(inc - allowed + gain, 2)))
    return rows


DRD_RATES_CURRENT = (0.50, 0.65, 1.00)   # <20%, 20%-<80%, >=80% ownership (IRC 243 post-TCJA)
DRD_RATES_PRE2018 = (0.70, 0.80, 1.00)   # pre-TCJA rates (simplified method)


def drd_rate(ownership_pct: float, rates: Sequence[float] = DRD_RATES_CURRENT) -> float:
    if ownership_pct >= 0.80:
        return rates[2]
    if ownership_pct >= 0.20:
        return rates[1]
    return rates[0]


@dataclass
class CorpTaxResult:
    taxable_income_before_special: float
    drd: float
    charitable_allowed: float
    nol_used: float
    taxable_income: float
    tax: float
    after_tax_income: float


def c_corp_tax(
    gross_income: float,
    deductions: float,
    dividends_received: float = 0.0,
    ownership_pct_of_payer: float = 0.0,
    charitable_contributions: float = 0.0,
    nol_carryforward: float = 0.0,
    year: int = DEFAULT_YEAR,
    drd_rates: Sequence[float] | None = None,
    method: str = "law",
) -> CorpTaxResult:
    """Form 1120 simplified. ``gross_income`` excludes ``dividends_received``.
    Dividends the corporation *pays* are not deductible (double taxation).
    DRD taxable-income limitation is applied (50%/65% DRD limited to that % of TI).
    ``method="simplified"`` uses the pre-2018 70%/80%/100% DRD."""
    if drd_rates is None:
        drd_rates = DRD_RATES_PRE2018 if method == "simplified" else DRD_RATES_CURRENT
    ti_pre = gross_income + dividends_received - deductions
    char_base = ti_pre
    floor = param("corp_charity_floor", year) * max(0.0, char_base)
    char = min(max(0.0, charitable_contributions - floor), param("corp_charity_limit", year) * max(0.0, char_base))
    ti_after_char = ti_pre - char
    rate = drd_rate(ownership_pct_of_payer, drd_rates)
    drd = dividends_received * rate
    if rate < 1.0 and ti_after_char - drd > 0:   # TI limitation doesn't apply if DRD creates/increases NOL
        drd = min(drd, rate * max(0.0, ti_after_char))
    ti_pre_nol = ti_after_char - drd
    nol = min(nol_carryforward, param("nol_pct_limit", year) * max(0.0, ti_pre_nol))
    ti = ti_pre_nol - nol
    tax = max(0.0, ti) * param("corp_rate", year)
    return CorpTaxResult(round(ti_pre, 2), round(drd, 2), round(char, 2), round(nol, 2), round(ti, 2),
                         round(tax, 2), round(ti_pre - tax, 2))


def double_tax_burden(pretax_corp_income: float, shareholder_dividend_rate: float,
                      year: int = DEFAULT_YEAR) -> dict:
    """Combined corporate + shareholder tax if all after-tax profit is distributed."""
    corp = pretax_corp_income * param("corp_rate", year)
    div = pretax_corp_income - corp
    sh = div * shareholder_dividend_rate
    return {"corporate_tax": round(corp, 2), "dividend": round(div, 2), "shareholder_tax": round(sh, 2),
            "total_tax": round(corp + sh, 2), "effective_rate": (corp + sh) / pretax_corp_income if pretax_corp_income else 0.0}
