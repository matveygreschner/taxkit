"""taxkit - a tested U.S. federal income tax engine (tax years 2025-2026, OBBBA)
with a generated, formula-driven spreadsheet that works in Excel and Google Sheets."""

__version__ = "1.0.0"

from .params import DEFAULT_YEAR, STATUSES, YEARS, param  # noqa: F401
from .rates import income_tax, ordinary_tax  # noqa: F401
