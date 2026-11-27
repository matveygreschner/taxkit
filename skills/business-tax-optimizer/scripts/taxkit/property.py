"""Property transactions: amount realized, basis, gain, capital netting,
home sale exclusion, foreclosure, stock basis."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .params import DEFAULT_YEAR, param


def amount_realized(cash: float = 0.0, fmv_property_received: float = 0.0,
                    debt_relief: float = 0.0, selling_expenses: float = 0.0) -> float:
    """Money + FMV of property + liabilities assumed by buyer - selling expenses."""
    return round(cash + fmv_property_received + debt_relief - selling_expenses, 2)


def adjusted_basis(original_cost: float, improvements: float = 0.0, cost_recovery: float = 0.0) -> float:
    """Cost + capital improvements - depreciation/cost recovery. Repairs are NOT added."""
    return round(original_cost + improvements - cost_recovery, 2)


@dataclass
class SaleResult:
    amount_realized: float
    adjusted_basis: float
    realized: float
    recognized: float
    excluded: float
    notes: List[str] = field(default_factory=list)


def sale(amount_realized_: float, adjusted_basis_: float, personal_use: bool = False,
         sec121_exclusion: float = 0.0) -> SaleResult:
    """Realized vs recognized gain. Losses on personal-use assets are not recognized."""
    realized = amount_realized_ - adjusted_basis_
    notes = []
    excluded = 0.0
    recognized = realized
    if realized < 0 and personal_use:
        recognized = 0.0
        notes.append("Loss on personal-use property is not deductible.")
    if realized > 0 and sec121_exclusion:
        excluded = min(realized, sec121_exclusion)
        recognized = realized - excluded
    return SaleResult(amount_realized_, adjusted_basis_, round(realized, 2), round(recognized, 2),
                      round(excluded, 2), notes)


def home_sale_exclusion(status: str, year: int = DEFAULT_YEAR, months_owned: int = 24, months_used: int = 24,
                        partial_reason: bool = False) -> float:
    """Sec. 121: $250K / $500K if owned AND used 24 of the last 60 months.
    Reduced exclusion (months/24) for health, job change or unforeseen events."""
    full = param("home_sale_exclusion", year, status)
    qualifying = min(months_owned, months_used)
    if qualifying >= 24:
        return full
    if partial_reason:
        return round(full * qualifying / 24, 2)
    return 0.0


@dataclass
class StockLot:
    shares: float
    total_basis: float

    @property
    def basis_per_share(self) -> float:
        return self.total_basis / self.shares if self.shares else 0.0


def stock_after_split_or_stock_dividend(lot: StockLot, ratio: float) -> StockLot:
    """A stock split or nontaxable stock dividend spreads the same basis over more shares.
    ``ratio`` = new shares per old share (2-for-1 split = 2.0, 10% stock dividend = 1.10).
    Cash dividends do NOT change basis."""
    return StockLot(lot.shares * ratio, lot.total_basis)


@dataclass
class NettingResult:
    net_short_term: float
    net_long_term: float
    net: float
    deductible_loss: float          # loss allowed against ordinary income (positive number)
    st_carryforward: float
    lt_carryforward: float
    taxable_st_gain: float
    taxable_lt_gain: float


def net_capital_gains(st_gains: float = 0.0, st_losses: float = 0.0, lt_gains: float = 0.0,
                      lt_losses: float = 0.0, st_carryover: float = 0.0, lt_carryover: float = 0.0,
                      status: str = "S", year: int = DEFAULT_YEAR,
                      taxable_income: float | None = None) -> NettingResult:
    """Net ST and LT separately, offset across, apply the $3,000 ($1,500 MFS)
    limit, and carry the rest forward keeping its character.
    Pass losses and carryovers as positive numbers.

    ``taxable_income`` (Form 1040 line 15 *before* flooring at zero, after the loss deduction)
    applies the Capital Loss Carryover Worksheet: only the part of the deduction actually absorbed
    by income reduces the carryover. If omitted, the full deduction is assumed absorbed."""
    nst = st_gains - st_losses - st_carryover
    nlt = lt_gains - lt_losses - lt_carryover
    net = nst + nlt
    limit = param("cap_loss_limit", year, status)
    if net >= 0:
        if nst >= 0 and nlt >= 0:
            return NettingResult(nst, nlt, net, 0.0, 0.0, 0.0, nst, nlt)
        if nst < 0:   # ST loss absorbed by LT gain
            return NettingResult(nst, nlt, net, 0.0, 0.0, 0.0, 0.0, net)
        return NettingResult(nst, nlt, net, 0.0, 0.0, 0.0, net, 0.0)
    # Net loss: ST losses are used first against ordinary income.
    loss = -net
    ded = min(loss, limit)
    if nlt >= 0:          # only ST loss remains
        st_left, lt_left = loss, 0.0
    elif nst >= 0:        # only LT loss remains
        st_left, lt_left = 0.0, loss
    else:                 # both negative
        st_left, lt_left = -nst, -nlt
    used = ded if taxable_income is None else min(ded, max(0.0, taxable_income + ded))
    st_cf = max(0.0, st_left - used)
    lt_cf = lt_left - max(0.0, used - st_left)
    return NettingResult(nst, nlt, net, ded, round(st_cf, 2), round(lt_cf, 2), 0.0, 0.0)


@dataclass
class ForeclosureResult:
    gain_on_disposition: float
    cancellation_of_debt_income: float


def foreclosure(debt: float, basis: float, fmv: float, recourse: bool) -> ForeclosureResult:
    """Recourse: gain = FMV - basis, COD income = debt - FMV.
    Non-recourse: treated as a sale for the full debt; gain = debt - basis."""
    if recourse:
        return ForeclosureResult(round(fmv - basis, 2), round(max(0.0, debt - fmv), 2))
    return ForeclosureResult(round(debt - basis, 2), 0.0)


def converted_property_basis(adjusted_basis_: float, fmv_at_conversion: float) -> float:
    """Personal-use asset converted to business use: depreciable basis is the
    lower of adjusted basis or FMV."""
    return min(adjusted_basis_, fmv_at_conversion)


def gift_basis(donor_basis: float, fmv_at_gift: float, sale_price: float) -> float:
    """Dual-basis rule: if FMV < donor basis at gift, use FMV for losses and donor
    basis for gains (no gain/loss in between)."""
    if fmv_at_gift >= donor_basis:
        return donor_basis
    if sale_price > donor_basis:
        return donor_basis
    if sale_price < fmv_at_gift:
        return fmv_at_gift
    return sale_price
