"""Estimated tax: IRC 6654 safe harbors and the Form 2210 underpayment penalty (regular method).

Design rules (see docs/ROADMAP.md):
* The penalty arithmetic is year-independent: it takes required installments, payments and a rate
  source, so it can be tested against IRS examples from any year.
* Unknown rates are never filled in silently. A quarter missing from the bundled IRC 6621 table must
  come in as a caller-supplied override, or the caller must opt in to ``rate_assumption="hold_last"``,
  which labels every affected figure as projected.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..live import UNDERPAYMENT_RATES, underpayment_rate
from ..params import param
from .dates import installment_due_dates, penalty_end_date, quarter_end, quarter_of


def _d(x) -> dt.date:
    return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x))


# ------------------------------------------------------------- safe harbor ---
@dataclass
class SafeHarborResult:
    year: int
    current_tax: float
    withholding: float
    exempt: bool
    exemption: str
    required_annual_payment: float
    method: str
    ninety_pct_current: float
    prior_year_amount: Optional[float]
    prior_year_pct: Optional[float]
    installments: List[dict]
    notes: List[str] = field(default_factory=list)


def _prior_year_tax(prior: dict, status: str, notes: list) -> float:
    """Prior-year tax for the safe harbor, combining or allocating when filing status changed
    (Form 2210 instructions / Pub. 505 ch. 4)."""
    tax = float(prior["tax"])
    pst = prior.get("status", status)
    if status == "MFJ" and pst == "MFS":
        sp = prior.get("spouse_separate_tax")
        if sp is None:
            raise ValueError("Filing jointly this year after separate returns last year: prior_year needs "
                             "spouse_separate_tax (the spouse's prior-year tax) to combine")
        notes.append("Prior-year tax combines both spouses' separate returns.")
        return tax + float(sp)
    if status == "MFS" and pst == "MFJ":
        own, sp = prior.get("own_separate_tax"), prior.get("spouse_separate_tax")
        if own is None or sp is None:
            raise ValueError("Filing separately this year after a joint return: prior_year needs "
                             "own_separate_tax and spouse_separate_tax (each figured as if MFS) to allocate")
        notes.append("Prior-year joint tax allocated by each spouse's separate-basis tax.")
        return tax * float(own) / (float(own) + float(sp)) if (own + sp) else 0.0
    return tax


def safe_harbor(current_tax: float, withholding: float, status: str, year: int = 2026,
                prior_year: Optional[dict] = None, citizen_or_resident: bool = True,
                farmer_fisherman: bool = False, filed_and_paid_by_jan31: bool = False) -> SafeHarborResult:
    """Required annual payment under IRC 6654(d) and the four installments, with the 6654(e) exceptions.

    ``current_tax`` is the Form 2210 line 4 amount (total tax less refundable credits).
    ``prior_year`` = {"tax", "agi", "status", "full_12_months": True, "spouse_separate_tax", "own_separate_tax"}
    or None when there is no prior-year return (then only the 90% harbor applies)."""
    notes: List[str] = []
    after_wh = current_tax - withholding
    base = SafeHarborResult(year, round(current_tax, 2), round(withholding, 2), False, "", 0.0, "", 0.0, None,
                            None, [], notes)
    if after_wh < param("est_min_balance", year):
        base.exempt, base.exemption = True, "IRC 6654(e)(1): tax after withholding is under $1,000"
        return base
    if prior_year is not None and prior_year.get("full_12_months", True) and citizen_or_resident \
            and float(prior_year.get("tax", 1)) == 0:
        base.exempt, base.exemption = True, "IRC 6654(e)(2): no tax liability for a full 12-month prior year"
        return base
    if farmer_fisherman:
        pct = param("est_farmer_pct", year)
        cur = pct * current_tax
        method = "66 2/3% of current-year tax (farmer/fisherman, IRC 6654(i))"
    else:
        cur = param("est_current_year_pct", year) * current_tax
        method = "90% of current-year tax"
    base.ninety_pct_current = round(cur, 2)
    req = cur
    if prior_year is None:
        notes.append("No prior-year return: only the current-year safe harbor applies.")
    elif not prior_year.get("full_12_months", True):
        notes.append("Prior year was a short year: the prior-year safe harbor doesn't apply (IRC 6654(d)(1)(B)(ii)).")
    else:
        ptax = _prior_year_tax(prior_year, status, notes)
        thr = param("est_high_agi_threshold", year, status)
        high = float(prior_year.get("agi", 0)) > thr
        ppct = param("est_prior_year_pct_high" if high else "est_prior_year_pct", year)
        if farmer_fisherman:
            ppct = 1.0        # the 110% rule doesn't apply to farmers and fishermen
        base.prior_year_amount, base.prior_year_pct = round(ppct * ptax, 2), ppct
        if ppct * ptax < req:
            req = ppct * ptax
            method = f"{ppct:.0%} of prior-year tax" + (" (prior AGI over $150K / $75K MFS)" if high else "")
    base.required_annual_payment = round(req, 2)
    base.method = method
    dates = installment_due_dates(year, farmer_fisherman)
    each = req / len(dates)
    base.installments = [{"due": dd, "required": round(each, 2), "cumulative": round(each * (i + 1), 2)}
                         for i, dd in enumerate(dates)]
    if filed_and_paid_by_jan31 and not farmer_fisherman:
        base.installments[-1]["excused"] = "IRC 6654(h): return filed and tax paid by January 31"
    return base


# --------------------------------------------------------- penalty ledger ---
@dataclass
class LedgerSegment:
    start: str        # first day of accrual (day after due date / previous application)
    end: str          # last day counted (date paid, capped at April 15)
    days: int
    rate: float
    rate_source: str
    amount: float     # underpayment balance outstanding in this segment
    penalty: float


@dataclass
class InstallmentRow:
    due: str
    required: float
    applied: List[dict]
    shortfall_at_due: float
    segments: List[LedgerSegment]
    penalty: float
    excused: str = ""


@dataclass
class PenaltyResult:
    year: int
    total_penalty: float
    rows: List[InstallmentRow]
    projected: bool
    rate_sources: Dict[str, str]
    notes: List[str] = field(default_factory=list)


def _rate_fn(overrides: Optional[Dict[str, float]], assumption: Optional[str], notes: list, sources: dict):
    last_q = sorted(UNDERPAYMENT_RATES)[-1]

    def rate(q: str) -> float:
        try:
            r = underpayment_rate(q, overrides)
        except ValueError:
            if assumption == "hold_last":
                val = (overrides or {}).get(last_q, UNDERPAYMENT_RATES[last_q])
                sources[q] = f"PROJECTED: held at {last_q} rate {val:.0%} (not yet announced)"
                return val
            raise ValueError(f"No IRC 6621 underpayment rate for {q}. Fetch it from "
                             "irs.gov/payments/quarterly-interest-rates and pass rate_overrides={'" + q +
                             "': rate}, or pass rate_assumption='hold_last' to project (results are labeled).")
        sources[q] = r["source"]
        return r["rate"]
    return rate


def _postponed(d: dt.date, windows: List[dict]) -> dt.date:
    for w in windows:
        if _d(w["start"]) <= d <= _d(w["end"]):
            return _d(w["end"])
    return d


def _accrue(balance: float, start: dt.date, end: dt.date, rate, sources: dict,
            windows: List[dict]) -> List[LedgerSegment]:
    """Interest on ``balance`` for each day from ``start`` through ``end`` inclusive, split at calendar
    quarters (where the IRC 6621 rate can change) and skipping IRC 7508A postponement windows."""
    one = dt.timedelta(days=1)
    segs: List[LedgerSegment] = []
    d = start
    while d <= end:
        inside = next((w for w in windows if _d(w["start"]) <= d <= _d(w["end"])), None)
        if inside:
            d = _d(inside["end"]) + one
            continue
        seg_end = min(end, quarter_end(d))
        later = [_d(w["start"]) for w in windows if d < _d(w["start"]) <= seg_end]
        if later:
            seg_end = min(later) - one
        q = quarter_of(d)
        r = rate(q)
        ylen = 366 if (d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)) else 365
        days = (seg_end - d).days + 1
        segs.append(LedgerSegment(d.isoformat(), seg_end.isoformat(), days, r, sources.get(q, ""),
                                  round(balance, 2), round(balance * r * days / ylen, 2)))
        d = seg_end + one
    return segs


def underpayment_penalty(required_installments: List[dict], payments: List[dict], withholding: float = 0.0,
                         year: int = 2026, withholding_dates: Optional[List[dict]] = None,
                         rate_overrides: Optional[Dict[str, float]] = None, rate_assumption: Optional[str] = None,
                         postponements: Optional[List[dict]] = None) -> PenaltyResult:
    """Form 2210 regular-method penalty.

    ``required_installments``: [{"due": "YYYY-MM-DD", "required": amount, "excused": optional}] (e.g. from
    ``safe_harbor``). ``payments``: estimated payments [{"date", "amount"}] (a prior-year overpayment
    applied is a payment dated the first due date). Withholding is treated as paid in equal parts on the
    installment due dates (IRC 6654(g)) unless ``withholding_dates`` [{"date", "amount"}] is given.

    Each payment is applied to the earliest unpaid required installment (IRC 6654(b)(3)); amounts beyond
    what is due carry forward to later installments. The penalty on each underpayment runs from the day
    after its due date through the day it is paid, never past April 15 of the following year, at the
    IRC 6621 rate for each calendar quarter.
    """
    notes: List[str] = []
    sources: Dict[str, str] = {}
    windows = postponements or []
    rate = _rate_fn(rate_overrides, rate_assumption, notes, sources)
    inst = sorted(({"due": _postponed(_d(i["due"]), windows), "required": float(i["required"]),
                    "excused": i.get("excused", "")} for i in required_installments), key=lambda x: x["due"])
    if any(_postponed(_d(i["due"]), windows) != _d(i["due"]) for i in required_installments):
        notes.append("Some due dates fall in a disaster postponement window (IRC 7508A) and were moved to its end.")
    pays = [{"date": _d(p["date"]), "amount": float(p["amount"]), "kind": "estimated payment"} for p in payments]
    if withholding_dates:
        pays += [{"date": _d(p["date"]), "amount": float(p["amount"]), "kind": "withholding"} for p in withholding_dates]
    elif withholding:
        n = len(inst)
        pays += [{"date": i["due"], "amount": withholding / n, "kind": "withholding (deemed paid evenly)"} for i in inst]
    pays.sort(key=lambda p: p["date"])
    end_cap = penalty_end_date(year)

    balances = [i["required"] for i in inst]
    applied: List[List[dict]] = [[] for _ in inst]
    # Apply payments in date order to the earliest installment that still has a balance.
    for p in pays:
        amt = p["amount"]
        for k in range(len(inst)):
            if amt <= 1e-9:
                break
            if balances[k] <= 1e-9:
                continue
            use = min(amt, balances[k])
            balances[k] -= use
            amt -= use
            applied[k].append({"date": p["date"].isoformat(), "amount": round(use, 2), "kind": p["kind"]})
        if amt > 1e-9:
            notes.append(f"{p['date'].isoformat()}: ${amt:,.2f} paid beyond all required installments.")

    rows: List[InstallmentRow] = []
    for k, i in enumerate(inst):
        due = i["due"]
        on_time = sum(a["amount"] for a in applied[k] if _d(a["date"]) <= due)
        shortfall = max(0.0, i["required"] - on_time)
        segs: List[LedgerSegment] = []
        if not i["excused"] and shortfall > 0.005:
            outstanding = shortfall
            start = due + dt.timedelta(days=1)
            late = sorted((a for a in applied[k] if _d(a["date"]) > due), key=lambda a: a["date"])
            for a in late:
                stop = min(_d(a["date"]), end_cap)
                if stop >= start:
                    segs += _accrue(outstanding, start, stop, rate, sources, windows)
                outstanding -= a["amount"]
                start = max(start, stop + dt.timedelta(days=1))
                if outstanding <= 0.005 or stop >= end_cap:
                    break
            if outstanding > 0.005 and start <= end_cap:
                segs += _accrue(outstanding, start, end_cap, rate, sources, windows)
        pen = round(sum(s.penalty for s in segs), 2)
        rows.append(InstallmentRow(due.isoformat(), round(i["required"], 2), applied[k], round(shortfall, 2),
                                   segs, pen, i["excused"]))
    projected = any(v.startswith("PROJECTED") for v in sources.values())
    if projected:
        notes.append("Some quarters' rates are not yet announced; figures using them are projected.")
    return PenaltyResult(year, round(sum(r.penalty for r in rows), 2), rows, projected, sources, notes)


# --------------------------------------------------------------- vouchers ---
def estimate_vouchers(required_annual_payment: float, expected_withholding: float = 0.0, year: int = 2026,
                      farmer_fisherman: bool = False) -> dict:
    """Form 1040-ES amounts: (required annual payment - expected withholding) split over the due dates."""
    dates = installment_due_dates(year, farmer_fisherman)
    need = max(0.0, required_annual_payment - expected_withholding)
    each = round(need / len(dates), 2)
    return {"year": year, "total_estimates": round(need, 2),
            "vouchers": [{"due": d, "amount": each} for d in dates],
            "note": "Withholding counts as paid evenly through the year, so extra withholding late in the year "
                    "covers earlier quarters; a voucher payment counts only from the day it is paid."}
