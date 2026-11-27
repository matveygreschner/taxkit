"""Retirement contributions: IRA deduction, Roth limit, SEP."""
from __future__ import annotations

import math

from .params import DEFAULT_YEAR, param


def _phase_out(limit: float, magi: float, start: float, rng: float, floor_200: bool) -> float:
    if magi <= start:
        return limit
    if magi >= start + rng:
        return 0.0
    reduced = limit * (start + rng - magi) / rng
    reduced = math.ceil(reduced / 10.0) * 10.0          # IRS rounds up to the next $10
    if floor_200:
        reduced = max(reduced, 200.0)
    return min(limit, reduced)


def ira_contribution_limit(compensation: float, age: int = 30, year: int = DEFAULT_YEAR) -> float:
    lim = param("ira_limit", year) + (param("ira_catchup", year) if age >= 50 else 0)
    return min(lim, max(0.0, compensation))


def traditional_ira_deduction(contribution: float, magi: float, status: str, covered_by_plan: bool,
                              spouse_covered: bool = False, compensation: float = 1e12, age: int = 30,
                              year: int = DEFAULT_YEAR) -> float:
    """Deductible traditional IRA contribution.
    Phase-out applies if the taxpayer is covered, or (MFJ) only the spouse is covered.
    A partially phased-out deduction is rounded up to $10 with a $200 minimum."""
    contrib = min(contribution, ira_contribution_limit(compensation, age, year))
    if covered_by_plan:
        start = param("ira_phase_start_covered", year, status)
        rng = param("ira_phase_range_covered", year, status)
    elif spouse_covered and status == "MFJ":
        start, rng = param("ira_phase_start_spouse", year), 10_000
    else:
        return contrib
    allowed = _phase_out(param("ira_limit", year) + (param("ira_catchup", year) if age >= 50 else 0),
                         magi, start, rng, floor_200=True)
    return min(contrib, allowed)


def roth_contribution_limit(magi: float, status: str, compensation: float = 1e12, age: int = 30,
                            year: int = DEFAULT_YEAR) -> float:
    full = ira_contribution_limit(compensation, age, year)
    return _phase_out(full, magi, param("roth_phase_start", year, status), param("roth_phase_range", year, status),
                      floor_200=True)


def sep_deduction(net_se_income: float, half_se_tax: float = 0.0, year: int = DEFAULT_YEAR,
                  use_shortcut: bool | None = None, method: str = "simplified") -> float:
    """SEP-IRA for a self-employed person.

    The statutory computation is 25% of compensation = 20% of (net SE income -
    1/2 SE tax). The common shortcut is "20% of self-employment income"; set
    ``use_shortcut=False`` to subtract the half SE tax first."""
    if use_shortcut is None:
        use_shortcut = method == "simplified"
    base = net_se_income if use_shortcut else net_se_income - half_se_tax
    return round(min(param("sep_pct_se", year) * max(0.0, base), param("dc_limit", year)), 2)
