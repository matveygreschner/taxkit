"""Rate-schedule math: ordinary brackets and the capital-gain worksheet.

The key idea (used identically in the Excel workbook) is a *cumulative tax
function* ``T(x) = sum_i max(0, x - lower_i) * (rate_i - rate_{i-1})``.
The tax on a *layer* of income from ``a`` to ``b`` is then ``T(b) - T(a)``,
which lets us stack ordinary income, 25% / 28% gains and 0/15/20% gains in the
order the Schedule D Tax Worksheet does.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

from .params import DEFAULT_YEAR, capital_gain_brackets, ordinary_brackets

Schedule = Sequence[Tuple[float, float]]


def cumulative_tax(x: float, schedule: Schedule, cap: float | None = None) -> float:
    """Tax on income ``0..x`` under ``schedule``; rates optionally capped at ``cap``."""
    total, prev = 0.0, 0.0
    for lower, rate in schedule:
        r = min(rate, cap) if cap is not None else rate
        if x > lower:
            total += (x - lower) * (r - prev)
        prev = r
    return total


def layer_tax(a: float, b: float, schedule: Schedule, cap: float | None = None) -> float:
    """Tax on the slice of income between ``a`` and ``b`` (a <= b)."""
    return cumulative_tax(b, schedule, cap) - cumulative_tax(a, schedule, cap)


def min_schedule(year: int, status: str) -> List[Tuple[float, float]]:
    """The simplified 'pick smaller' schedule: at every ordinary or capital-gain breakpoint,
    the rate is min(ordinary rate, capital-gain rate)."""
    o = ordinary_brackets(year, status)
    g = capital_gain_brackets(year, status)
    pts = sorted({p for p, _ in o} | {p for p, _ in g})
    return [(p, min([r for lo, r in o if lo <= p][-1], [r for lo, r in g if lo <= p][-1])) for p in pts]


def ordinary_tax(taxable_income: float, status: str, year: int = DEFAULT_YEAR) -> float:
    """Regular tax from the rate schedule (not the IRS tax table)."""
    return round(cumulative_tax(max(0.0, taxable_income), ordinary_brackets(year, status)), 2)


@dataclass
class BracketRow:
    lower: float
    upper: float | None
    rate: float
    amount_in_bracket: float
    tax: float


def bracket_breakdown(taxable_income: float, status: str, year: int = DEFAULT_YEAR) -> List[BracketRow]:
    """Bracket-by-bracket table."""
    sched = ordinary_brackets(year, status)
    rows = []
    for i, (lower, rate) in enumerate(sched):
        upper = sched[i + 1][0] if i + 1 < len(sched) else None
        top = taxable_income if upper is None else min(taxable_income, upper)
        amt = max(0.0, top - lower)
        rows.append(BracketRow(lower, upper, rate, amt, round(amt * rate, 2)))
    return rows


def marginal_rate(taxable_income: float, status: str, year: int = DEFAULT_YEAR) -> float:
    rate = 0.10
    for lower, r in ordinary_brackets(year, status):
        if taxable_income > lower:
            rate = r
    return rate


@dataclass
class TaxResult:
    taxable_income: float
    regular_tax: float               # all income at ordinary rates
    tax: float                       # final income tax (min of regular / worksheet)
    ordinary_portion: float
    tax_on_ordinary: float
    tax_on_unrecaptured_1250: float = 0.0
    tax_on_collectibles: float = 0.0
    tax_on_ancg: float = 0.0
    ancg_at_0: float = 0.0
    ancg_at_15: float = 0.0
    ancg_at_20: float = 0.0
    marginal_rate: float = 0.0
    effective_rate: float = 0.0
    notes: List[str] = field(default_factory=list)


def income_tax(
    taxable_income: float,
    status: str,
    year: int = DEFAULT_YEAR,
    qualified_dividends: float = 0.0,
    net_ltcg: float = 0.0,
    unrecaptured_1250: float = 0.0,
    collectibles_gain: float = 0.0,
    method: str = "law",
) -> TaxResult:
    """Income tax with preferential rates under IRC 1(h) (the Schedule D Tax Worksheet).

    ``net_ltcg`` is the net capital gain *including* any unrecaptured 1250 and collectibles gain
    (the smaller of Schedule D lines 15 and 16).

    Statutory structure: (A) ordinary rates apply to the greater of taxable income minus net capital
    gain, or the lesser of the income taxed below 25% and taxable income minus adjusted net capital
    gain (ANCG) - so 25%/28% gain sitting in low brackets is taxed at ordinary rates; (B)-(D) ANCG is
    taxed at 0/15/20% by its position directly above amount (A); (E)-(F) the rest of the unrecaptured
    1250 gain is taxed at 25%, then 28%-rate gain at 28%. Final tax = smaller of that or regular tax.

    ``method="simplified"`` taxes the ANCG band-by-band at the smaller of the ordinary and capital-gain
    rate, a common hand-computation shortcut.
    """
    if method not in ("law", "simplified"):
        raise ValueError("method must be 'law' or 'simplified'")
    ti = max(0.0, taxable_income)
    ord_sched = ordinary_brackets(year, status)
    cg_sched = capital_gain_brackets(year, status)

    net_cap = max(0.0, net_ltcg)
    pref_total = min(ti, max(0.0, qualified_dividends) + net_cap)
    u1250 = min(max(0.0, unrecaptured_1250), net_cap)
    coll = min(max(0.0, collectibles_gain), net_cap - u1250)
    special = min(u1250 + coll, pref_total)
    u1250 = min(u1250, special)
    coll = special - u1250
    ancg = pref_total - special

    below25 = ord_sched[4][0]                       # income taxed below 25% = top of the 24% bracket
    amt_a = max(ti - pref_total, min(below25, ti - ancg))
    flat = max(0.0, ti - amt_a - ancg)              # special gain not absorbed into amount (A)
    at25 = min(u1250, flat)
    at28 = flat - at25

    t_ord = cumulative_tax(amt_a, ord_sched)
    sched = min_schedule(year, status) if method == "simplified" else cg_sched
    t_ancg = layer_tax(amt_a, amt_a + ancg, sched)
    t_1250 = 0.25 * at25
    t_coll = 0.28 * at28

    top0, top15 = cg_sched[1][0], cg_sched[2][0]
    at0 = max(0.0, min(amt_a + ancg, top0) - amt_a)
    at15 = max(0.0, min(amt_a + ancg, top15) - max(amt_a, top0))
    at20 = max(0.0, ancg - at0 - at15)

    regular = cumulative_tax(ti, ord_sched)
    worksheet = t_ord + t_ancg + t_1250 + t_coll
    final = min(regular, worksheet)
    res = TaxResult(
        taxable_income=ti,
        regular_tax=round(regular, 2),
        tax=round(final, 2),
        ordinary_portion=amt_a,
        tax_on_ordinary=round(t_ord, 2),
        tax_on_unrecaptured_1250=round(t_1250, 2),
        tax_on_collectibles=round(t_coll, 2),
        tax_on_ancg=round(t_ancg, 2),
        ancg_at_0=at0,
        ancg_at_15=at15,
        ancg_at_20=at20,
        marginal_rate=marginal_rate(ti, status, year),
        effective_rate=(final / ti) if ti else 0.0,
    )
    if pref_total and worksheet > regular:
        res.notes.append("Regular tax was lower than the worksheet; regular tax used.")
    return res


def per_band_min_tax(
    taxable_income: float, preferential_income: float, status: str, year: int = DEFAULT_YEAR
) -> float:
    """The simplified method: split income at every
    ordinary *and* capital-gain breakpoint and tax each preferential slice at the
    smaller of the ordinary and capital-gain rate for that slice.

    This is NOT the statutory computation - it can understate tax when gains fall
    in a 12% ordinary band above the 0% capital-gain threshold. Provided so you
    can match a hand-computed answer and explain the difference.
    """
    ti = max(0.0, taxable_income)
    pref = min(ti, max(0.0, preferential_income))
    ordinary = ti - pref
    ord_sched = ordinary_brackets(year, status)
    cg_sched = capital_gain_brackets(year, status)
    points = sorted({p for p, _ in ord_sched} | {p for p, _ in cg_sched} | {ordinary, ti})
    total = cumulative_tax(ordinary, ord_sched)
    for lo, hi in zip(points, points[1:]):
        lo2, hi2 = max(lo, ordinary), min(hi, ti)
        if hi2 <= lo2:
            continue
        r_ord = [r for p, r in ord_sched if p <= lo2][-1]
        r_cg = [r for p, r in cg_sched if p <= lo2][-1]
        total += (hi2 - lo2) * min(r_ord, r_cg)
    return round(total, 2)
