"""Schedule A itemized deductions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .params import DEFAULT_YEAR, param


def medical_deduction(expenses: float, agi: float, year: int = DEFAULT_YEAR) -> float:
    return round(max(0.0, expenses - param("medical_floor", year) * max(0.0, agi)), 2)


def salt_cap(magi: float, status: str, year: int = DEFAULT_YEAR) -> float:
    """OBBBA SALT cap: $40,000 (2025) / $40,400 (2026), reduced 30% of MAGI over
    $500K / $505K, never below $10,000 ($5,000 MFS)."""
    cap = param("salt_cap", year, status)
    over = max(0.0, magi - param("salt_phase_start", year, status))
    # MFS: the reduction is figured on the full cap and then halved, i.e. 15% of the excess.
    rate = param("salt_phase_rate", year) * (0.5 if status == "MFS" else 1.0)
    return max(param("salt_floor", year, status), cap - rate * over)


def salt_deduction(state_local_taxes: float, magi: float, status: str, year: int = DEFAULT_YEAR) -> float:
    return round(min(state_local_taxes, salt_cap(magi, status, year)), 2)


def mortgage_interest_deduction(
    interest_paid: float, average_balance: float, status: str, year: int = DEFAULT_YEAR,
    grandfathered: bool = False,
) -> float:
    """Pro-rate interest when acquisition debt exceeds $750K ($1M if pre-12/16/2017)."""
    limit = param("mortgage_limit", year, status)
    if grandfathered:
        limit = 500_000 if status == "MFS" else 1_000_000
    if average_balance <= limit or average_balance <= 0:
        return round(interest_paid, 2)
    return round(interest_paid * limit / average_balance, 2)


def investment_interest_deduction(interest: float, net_investment_income: float) -> tuple:
    """Limited to net investment income; excess carries forward indefinitely."""
    allowed = min(interest, max(0.0, net_investment_income))
    return round(allowed, 2), round(interest - allowed, 2)


@dataclass
class CharityResult:
    allowed_before_floor: float
    floor: float
    deduction: float
    carryforward: float
    notes: List[str] = field(default_factory=list)


def charitable_deduction(
    agi: float,
    cash_public: float = 0.0,
    property_ltcg_public: float = 0.0,
    cash_private: float = 0.0,
    property_ltcg_private: float = 0.0,
    year: int = DEFAULT_YEAR,
) -> CharityResult:
    """Simplified IRC 170(b) ordering: each bucket limited to its %-of-AGI cap
    and the total limited to 60% of AGI. 2026+: only the excess over 0.5% of
    AGI is deductible. Property amounts are FMV for LTCG property; use basis
    for ordinary-income / short-term property."""
    agi = max(0.0, agi)
    caps = [
        (cash_public, param("charity_cash_public_pct", year)),
        (property_ltcg_public, param("charity_property_public_pct", year)),
        (cash_private, param("charity_cash_private_pct", year)),
        (property_ltcg_private, param("charity_property_private_pct", year)),
    ]
    allowed = sum(min(amt, pct * agi) for amt, pct in caps)
    allowed = min(allowed, param("charity_cash_public_pct", year) * agi)
    total = cash_public + property_ltcg_public + cash_private + property_ltcg_private
    floor = param("charity_floor_pct", year) * agi
    ded = max(0.0, allowed - floor)
    res = CharityResult(round(allowed, 2), round(floor, 2), round(ded, 2), round(total - allowed, 2))
    if total > allowed:
        res.notes.append("Excess over AGI limits carries forward 5 years.")
    return res


def section_68_reduction(itemized_total: float, taxable_income_plus_itemized: float, status: str,
                         year: int = DEFAULT_YEAR) -> float:
    """OBBBA Sec. 68 (2026+): itemized deductions are reduced by 2/37 of the lesser of the itemized
    deductions or the amount by which taxable income plus itemized deductions exceeds the start of
    the 37% bracket."""
    from .params import ordinary_brackets
    if not param("itemized_limit_2_37", year):
        return 0.0
    top = ordinary_brackets(year, status)[6][0]
    return round(2 / 37 * min(max(0.0, itemized_total), max(0.0, taxable_income_plus_itemized - top)), 2)


def gambling_loss_deduction(losses: float, winnings: float, year: int = DEFAULT_YEAR) -> float:
    """2026+: 90% of losses, capped at winnings (OBBBA)."""
    return round(min(losses * param("gambling_loss_pct", year), winnings), 2)


@dataclass
class ItemizedResult:
    medical: float
    salt: float
    mortgage_interest: float
    investment_interest: float
    charity: float
    casualty: float
    gambling: float
    other: float

    @property
    def total(self) -> float:
        return round(self.medical + self.salt + self.mortgage_interest + self.investment_interest
                     + self.charity + self.casualty + self.gambling + self.other, 2)


def itemized_deductions(
    agi: float,
    status: str,
    year: int = DEFAULT_YEAR,
    medical_expenses: float = 0.0,
    state_local_taxes: float = 0.0,
    mortgage_interest: float = 0.0,
    mortgage_avg_balance: float = 0.0,
    investment_interest: float = 0.0,
    net_investment_income: float = 0.0,
    charity_cash_public: float = 0.0,
    charity_property_public: float = 0.0,
    charity_cash_private: float = 0.0,
    charity_property_private: float = 0.0,
    casualty_loss_allowed: float = 0.0,
    gambling_losses: float = 0.0,
    gambling_winnings: float = 0.0,
    other: float = 0.0,
    magi: float | None = None,
) -> ItemizedResult:
    magi = agi if magi is None else magi
    return ItemizedResult(
        medical=medical_deduction(medical_expenses, agi, year),
        salt=salt_deduction(state_local_taxes, magi, status, year),
        mortgage_interest=mortgage_interest_deduction(mortgage_interest, mortgage_avg_balance, status, year),
        investment_interest=investment_interest_deduction(investment_interest, net_investment_income)[0],
        charity=charitable_deduction(agi, charity_cash_public, charity_property_public,
                                     charity_cash_private, charity_property_private, year).deduction,
        casualty=casualty_loss_allowed,
        gambling=gambling_loss_deduction(gambling_losses, gambling_winnings, year),
        other=other,
    )
