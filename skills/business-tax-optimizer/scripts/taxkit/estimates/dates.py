"""Due dates for estimated tax: IRC 6654(c) installment dates shifted under IRC 7503 when they fall
on a Saturday, Sunday or legal holiday (federal holidays plus DC Emancipation Day, Apr 16)."""
from __future__ import annotations

import datetime as dt
from typing import List, Set


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    d = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: dt.date) -> dt.date:
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def legal_holidays(year: int) -> Set[dt.date]:
    """Federal legal holidays (5 U.S.C. 6103) as observed, plus DC Emancipation Day (IRC 7503)."""
    mon, thu = 0, 3
    days = {
        _observed(dt.date(year, 1, 1)),
        _nth_weekday(year, 1, mon, 3),              # Martin Luther King Jr. Day
        _nth_weekday(year, 2, mon, 3),              # Washington's Birthday
        _observed(dt.date(year, 4, 16)),            # DC Emancipation Day
        _last_weekday(year, 5, mon),                # Memorial Day
        _observed(dt.date(year, 6, 19)),            # Juneteenth
        _observed(dt.date(year, 7, 4)),
        _nth_weekday(year, 9, mon, 1),              # Labor Day
        _nth_weekday(year, 10, mon, 2),             # Columbus Day
        _observed(dt.date(year, 11, 11)),
        _nth_weekday(year, 11, thu, 4),             # Thanksgiving
        _observed(dt.date(year, 12, 25)),
    }
    nxt = dt.date(year + 1, 1, 1)
    if nxt.weekday() == 5:                          # Jan 1 on a Saturday is observed Dec 31
        days.add(dt.date(year, 12, 31))
    return days


def next_business_day(d: dt.date) -> dt.date:
    while d.weekday() >= 5 or d in legal_holidays(d.year):
        d += dt.timedelta(days=1)
    return d


def installment_due_dates(year: int, farmer_fisherman: bool = False) -> List[str]:
    """The four 1040-ES due dates for ``year`` (Apr 15, Jun 15, Sep 15, Jan 15), shifted by IRC 7503.
    Farmers and fishermen pay one installment, on Jan 15 (IRC 6654(i))."""
    raw = [dt.date(year, 4, 15), dt.date(year, 6, 15), dt.date(year, 9, 15), dt.date(year + 1, 1, 15)]
    if farmer_fisherman:
        raw = raw[3:]
    return [next_business_day(d).isoformat() for d in raw]


def penalty_end_date(year: int) -> dt.date:
    """Form 2210 computes the penalty through April 15 of the following year (not shifted)."""
    return dt.date(year + 1, 4, 15)


def quarter_of(d: dt.date) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def quarter_end(d: dt.date) -> dt.date:
    q = (d.month - 1) // 3 + 1
    return dt.date(d.year, 12, 31) if q == 4 else dt.date(d.year, 3 * q + 1, 1) - dt.timedelta(days=1)
