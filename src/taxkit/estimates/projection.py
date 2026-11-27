"""Year-end estimated tax projection: what's still owed under each safe harbor, the penalty if nothing
changes, and the remedies ranked by net benefit (penalty avoided minus the remedy's own cost)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..form1040 import Return1040, compute_return
from .core import _d, safe_harbor, underpayment_penalty
from .dates import installment_due_dates


@dataclass
class Remedy:
    name: str
    amount: float
    penalty_after: float
    penalty_avoided: float
    cost: float
    net_benefit: float
    recommended: bool
    how: str
    caveats: List[str] = field(default_factory=list)
    effort: int = 1          # 1 simplest; used to break ties in net benefit


@dataclass
class YearEndProjection:
    year: int
    as_of: str
    projected_total_tax: float
    withholding: float
    estimated_payments: float
    balance_due_at_filing: float
    safe_harbor: dict
    still_needed: Dict[str, float]
    penalty_if_nothing_changes: float
    remedies: List[Remedy]
    projected_rates: bool
    rate_sources: Dict[str, str]
    notes: List[str] = field(default_factory=list)


def _penalty(sh, payments, withholding, year, ro, ra) -> float:
    return underpayment_penalty(sh.installments, payments, withholding, year, rate_overrides=ro,
                                rate_assumption=ra).total_penalty


def _min_extra(fn, hi: float) -> Optional[float]:
    """Smallest whole-dollar x in [0, hi] with fn(x) == 0 (fn non-increasing), or None."""
    if fn(hi) > 0.004:
        return None
    lo, top = 0.0, hi
    while top - lo > 0.5:
        mid = (lo + top) / 2
        if fn(mid) > 0.004:
            lo = mid
        else:
            top = mid
    x = float(int(top) + (0 if top == int(top) else 1))
    return x


def year_end_projection(return_inputs: dict, estimated_payments: Optional[List[dict]] = None, as_of: str = "",
                        prior_year: Optional[dict] = None, has_wages: bool = True,
                        taxpayer_age: Optional[float] = None, ira: Optional[dict] = None,
                        citizen_or_resident: bool = True,
                        rate_overrides: Optional[Dict[str, float]] = None,
                        rate_assumption: Optional[str] = None) -> YearEndProjection:
    """Project the year's tax with the full Form 1040 engine and rank the ways to avoid the penalty.

    ``return_inputs``: Return1040 fields for the projected full year; ``withholding`` is total expected
    federal withholding for the year (including remaining paychecks). ``estimated_payments``:
    [{"date", "amount"}] already made or scheduled. ``prior_year``: as in ``safe_harbor``.
    ``ira``: {"balance", "rollover_dates_last_12_months": [], "cash_available_for_60_days",
    "withholding_rate": None (10% default, IRC 3405(b))} to evaluate the IRA withholding remedies.
    A 2026 penalty runs to April 15, 2027: pass ``rate_overrides`` for 2027 quarters (from irs.gov) or
    ``rate_assumption="hold_last"`` to project them (results are labeled)."""
    pays = list(estimated_payments or [])
    ri = dict(return_inputs)
    year = int(ri.get("year", 2026))
    status = ri.get("status", "S")
    when = _d(as_of) if as_of else dt.date.today()
    notes: List[str] = []
    r = compute_return(Return1040(**{k: v for k, v in ri.items() if k != "estimated_payments"}))
    cur_tax = round(r.total_tax - r.refundable_credits, 2)
    wh = float(ri.get("withholding", 0.0))
    est_total = sum(float(p["amount"]) for p in pays)
    sh = safe_harbor(cur_tax, wh, status, year, prior_year, citizen_or_resident)
    still = {}
    paid = wh + est_total
    still["current_year_90pct"] = round(max(0.0, sh.ninety_pct_current - paid), 2)
    if sh.prior_year_amount is not None:
        still["prior_year_harbor"] = round(max(0.0, sh.prior_year_amount - paid), 2)
    still["to_owe_nothing_at_filing"] = round(max(0.0, cur_tax - paid), 2)
    out = YearEndProjection(year, when.isoformat(), cur_tax, wh, est_total, round(cur_tax - paid, 2),
                            {"exempt": sh.exempt, "exemption": sh.exemption,
                             "required_annual_payment": sh.required_annual_payment, "method": sh.method,
                             "installments": sh.installments, "notes": sh.notes}, still, 0.0, [], False, {}, notes)
    if sh.exempt:
        notes.append(f"No underpayment penalty: {sh.exemption}.")
        return out
    ro, ra = rate_overrides, rate_assumption
    base = underpayment_penalty(sh.installments, pays, wh, year, rate_overrides=ro, rate_assumption=ra)
    out.penalty_if_nothing_changes = base.total_penalty
    out.projected_rates, out.rate_sources = base.projected, base.rate_sources
    if base.total_penalty <= 0:
        notes.append("Payments and withholding already meet every required installment.")
        return out
    remedies: List[Remedy] = []
    dec31 = dt.date(year, 12, 31)
    jan15 = installment_due_dates(year)[-1]

    # 1) Extra W-4 withholding before Dec 31 - counts as paid evenly, so it cures every quarter.
    x_wh = _min_extra(lambda x: _penalty(sh, pays, wh + x, year, ro, ra), sh.required_annual_payment)
    if has_wages and when <= dec31 and x_wh is not None:
        remedies.append(Remedy("Extra federal withholding from wages before Dec 31 (new W-4)", x_wh, 0.0,
                               base.total_penalty, 0.0, base.total_penalty, True,
                               f"Have ${x_wh:,.0f} more withheld from remaining {year} paychecks.",
                               ["Withholding counts as paid evenly through the year (IRC 6654(g)), so it fixes "
                                "earlier quarters too", "Needs enough remaining paychecks to absorb it"]))
    elif not has_wages:
        notes.append("No wages: the withholding remedy isn't available (unless via an IRA distribution).")

    # 2) Jan 15 estimated payment - fixes only the last installment.
    gap = max(0.0, sh.installments[-1]["cumulative"] - paid)
    if gap > 0:
        after = _penalty(sh, pays + [{"date": jan15, "amount": gap}], wh, year, ro, ra)
        remedies.append(Remedy(f"Estimated payment by {jan15}", round(gap, 2), after,
                               round(base.total_penalty - after, 2), 0.0, round(base.total_penalty - after, 2),
                               base.total_penalty - after > 0, f"Pay ${gap:,.2f} with the 4th 1040-ES voucher.",
                               ["Counts only from the day paid, so earlier quarters' shortfalls stay"], effort=1))

    # 3) / 4) IRA distribution with withholding (rolled back over, or kept).
    if ira is None:
        notes.append("IRA remedies not evaluated: no IRA input.")
    elif x_wh is not None:
        elected = ira.get("withholding_rate")
        rates = [(float(elected), False)] if elected is not None else [(0.10, True), (1.0, False)]
        cash = float(ira.get("cash_available_for_60_days", 0))
        recent = [d for d in ira.get("rollover_dates_last_12_months", []) if (when - _d(d)).days < 365]
        for rate, is_default in rates:
            gross = round(x_wh / rate, 2) if rate > 0 else None
            label = ("10% default withholding" if is_default else f"{rate:.0%} withholding elected on Form W-4R")
            if gross is None or gross > float(ira.get("balance", 0)):
                notes.append(f"IRA balance too small for the withholding remedy at {label}.")
                continue
            ok = not recent and cash >= x_wh
            why = []
            if recent:
                why.append("an IRA-to-IRA rollover was already done in the last 12 months (IRC 408(d)(3)(B))")
            if cash < x_wh:
                why.append(f"you receive ${gross - x_wh:,.0f} net but must redeposit the full ${gross:,.0f}, "
                           f"so you need ${x_wh:,.0f} of other cash for up to 60 days")
            remedies.append(Remedy(f"IRA distribution with {label}, rolled back over within 60 days", gross,
                                   0.0 if ok else base.total_penalty, base.total_penalty if ok else 0.0, 0.0,
                                   base.total_penalty if ok else 0.0, ok,
                                   f"Take ${gross:,.0f} from the IRA with ${x_wh:,.0f} withheld (you receive "
                                   f"${gross - x_wh:,.0f}); redeposit the full ${gross:,.0f} within 60 days using "
                                   f"${x_wh:,.0f} of other cash (IRC 408(d)(3)).",
                                   (["Default for nonperiodic IRA distributions (IRC 3405(b))"] if is_default else []) +
                                   (["Not available: " + "; ".join(why)] if why else
                                    ["Risk: missing the 60-day deadline makes it taxable; one rollover per 12 months"]),
                                   effort=3 if is_default else 2))
        # Kept (not rolled over): sized at the elected rate, else the 10% default.
        rate = float(elected) if elected is not None else 0.10
        gross = round(x_wh / rate, 2) if rate > 0 else 0.0
        if 0 < gross <= float(ira.get("balance", 0)):
            with_ira = compute_return(Return1040(**{**{k: v for k, v in ri.items() if k != "estimated_payments"},
                                                    "other_income": float(ri.get("other_income", 0)) + gross}))
            inc_tax = (with_ira.total_tax - with_ira.refundable_credits) - cur_tax
            early = 0.10 * gross if (taxpayer_age is not None and taxpayer_age < 59.5) else 0.0
            cost = round(inc_tax + early, 2)
            remedies.append(Remedy("IRA distribution with withholding, kept (not rolled over)", gross, 0.0,
                                   base.total_penalty, cost, round(base.total_penalty - cost, 2),
                                   base.total_penalty - cost > 0,
                                   f"Take ${gross:,.0f} with ${x_wh:,.0f} withheld and keep it.",
                                   [f"Adds ${inc_tax:,.2f} of income tax" +
                                    (f" and ${early:,.2f} of IRC 72(t) additional tax (under 59 1/2)" if early else "")],
                                   effort=2))
    remedies.sort(key=lambda m: (not m.recommended, -round(m.net_benefit, 2), m.cost, m.effort))
    out.remedies = remedies
    if out.projected_rates:
        notes.append("Penalty figures use projected rates for quarters not yet announced.")
    return out
