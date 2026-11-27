"""Estimated tax planning: IRC 6654 safe harbors, the Form 2210 penalty, year-end remedies."""
from __future__ import annotations

from .. import api
from .core import estimate_vouchers, safe_harbor, underpayment_penalty
from .dates import installment_due_dates

api.register("safe_harbor", safe_harbor)
api.register("underpayment_penalty", underpayment_penalty)
api.register("estimate_vouchers", estimate_vouchers)
api.register("installment_due_dates", installment_due_dates)

try:   # year-end projection lives in its own module
    from .projection import year_end_projection
    api.register("year_end_projection", year_end_projection)
except ImportError as e:   # pragma: no cover - only while the module is being written
    if e.name != "taxkit.estimates.projection":
        raise
