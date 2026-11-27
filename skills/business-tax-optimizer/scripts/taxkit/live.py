"""Live-data adapters: turn data fetched by connected tools (SEC XBRL facts, IRS rate tables)
into deterministic, checked inputs for the engine.

The engine never fetches anything itself - the model (or a script) pulls data through whatever
connector is available (an SEC filings MCP tool, a web fetch of irs.gov) and passes the raw rows
here. Everything returned carries its source and as-of date so a stale or mis-tagged figure is
visible rather than silently used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# us-gaap concepts used for an income tax profile (ASC 740 disclosures)
CONCEPTS = {
    "pretax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"],
    "tax": ["IncomeTaxExpenseBenefit"],
    "etr_tagged": ["EffectiveIncomeTaxRateContinuingOperations"],
    "statutory": ["EffectiveIncomeTaxRateReconciliationAtFederalStatutoryIncomeTaxRate"],
    "current_federal": ["CurrentFederalTaxExpenseBenefit"],
    "deferred_federal": ["DeferredFederalIncomeTaxExpenseBenefit"],
    "current_state": ["CurrentStateAndLocalTaxExpenseBenefit"],
    "deferred_state": ["DeferredStateAndLocalIncomeTaxExpenseBenefit"],
    "current_foreign": ["CurrentForeignTaxExpenseBenefit"],
    "deferred_foreign": ["DeferredForeignIncomeTaxExpenseBenefit"],
    "valuation_allowance": ["DeferredTaxAssetsValuationAllowance"],
    "utb": ["UnrecognizedTaxBenefits"],
    "cash_taxes": ["IncomeTaxesPaidNet", "IncomeTaxesPaid"],
}
DURATION = {"pretax", "tax", "etr_tagged", "statutory", "current_federal", "deferred_federal", "current_state",
            "deferred_state", "current_foreign", "deferred_foreign", "cash_taxes"}


@dataclass
class TaxYearProfile:
    fiscal_year_end: str
    pretax_income: Optional[float] = None
    income_tax_expense: Optional[float] = None
    etr_computed: Optional[float] = None
    etr_tagged: Optional[float] = None
    statutory_rate: Optional[float] = None
    current_tax: Optional[float] = None
    deferred_tax: Optional[float] = None
    current_share: Optional[float] = None
    cash_taxes_paid: Optional[float] = None
    valuation_allowance: Optional[float] = None
    unrecognized_tax_benefits: Optional[float] = None
    components: Dict[str, float] = field(default_factory=dict)
    checks: List[str] = field(default_factory=list)


@dataclass
class SecTaxProfile:
    company: str
    source: str
    as_of: str
    years: List[TaxYearProfile]
    observations: List[str] = field(default_factory=list)


def _num(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pick(facts: List[dict], names: List[str], end: str, duration: bool) -> Optional[float]:
    """First unsegmented (no dimension axes) fact for the concept names ending on ``end``."""
    for name in names:
        for f in facts:
            if f.get("concept") != name or f.get("axises") or f.get("axes"):
                continue
            if f.get("end_date") != end:
                continue
            if duration and not f.get("start_date"):
                continue
            if not duration and f.get("start_date"):
                continue
            if duration:   # annual periods only (~1 year)
                import datetime
                s = datetime.date.fromisoformat(f["start_date"])
                e = datetime.date.fromisoformat(f["end_date"])
                if not 350 <= (e - s).days <= 380:
                    continue
            v = _num(f.get("value"))
            if v is not None:
                return v
    return None


def sec_tax_profile(facts: List[dict], company: str = "", source: str = "SEC XBRL (10-K)", as_of: str = "",
                    statutory_rate: float = 0.21) -> SecTaxProfile:
    """Build a checked income tax profile from us-gaap XBRL facts (one 10-K carries ~3 years).

    ``facts``: rows with ``concept``, ``value``, ``end_date`` (and ``start_date`` for durations),
    and optional ``axises``/``axes`` - the shape SEC filing-facts tools return. Only facts with no
    dimensional axes are used, so segment / jurisdiction breakdowns don't double count.
    """
    if not isinstance(facts, list):
        raise ValueError("facts must be a list of XBRL fact rows")
    ends = sorted({f.get("end_date") for f in facts if f.get("concept") in CONCEPTS["tax"]
                   and not (f.get("axises") or f.get("axes")) and f.get("start_date")}, reverse=True)
    years = []
    for end in ends:
        g = {k: _pick(facts, names, end, k in DURATION) for k, names in CONCEPTS.items()}
        y = TaxYearProfile(end, g["pretax"], g["tax"], etr_tagged=g["etr_tagged"],
                           statutory_rate=g["statutory"] or statutory_rate,
                           cash_taxes_paid=g["cash_taxes"], valuation_allowance=g["valuation_allowance"],
                           unrecognized_tax_benefits=g["utb"])
        comps = {k: g[k] for k in ("current_federal", "deferred_federal", "current_state", "deferred_state",
                                   "current_foreign", "deferred_foreign") if g[k] is not None}
        y.components = comps
        cur = [v for k, v in comps.items() if k.startswith("current")]
        dfr = [v for k, v in comps.items() if k.startswith("deferred")]
        y.current_tax = sum(cur) if cur else None
        y.deferred_tax = sum(dfr) if dfr else None
        if y.pretax_income and y.income_tax_expense is not None:
            y.etr_computed = y.income_tax_expense / y.pretax_income
            if y.etr_tagged is not None and abs(y.etr_computed - y.etr_tagged) > 0.006:
                y.checks.append(f"Computed ETR {y.etr_computed:.1%} differs from tagged ETR {y.etr_tagged:.1%} - "
                                "check the pretax income concept used")
            gap = y.etr_computed - y.statutory_rate
            if abs(gap) >= 0.05:
                y.checks.append(f"ETR is {gap:+.1%} vs the {y.statutory_rate:.0%} statutory rate - the rate "
                                "reconciliation should explain it (ASU 2023-09 requires separate disclosure of "
                                "items >= 5% of statutory tax)")
        if y.current_tax is not None and y.deferred_tax is not None and y.income_tax_expense:
            total = y.current_tax + y.deferred_tax
            if len(comps) >= 6 and abs(total - y.income_tax_expense) > max(1.0, 0.005 * abs(y.income_tax_expense)):
                y.checks.append(f"Current + deferred components ({total:,.0f}) don't sum to total tax expense "
                                f"({y.income_tax_expense:,.0f})")
            y.current_share = y.current_tax / total if total else None
            if len(comps) < 6:
                y.checks.append("Only some jurisdictions' current/deferred components were found; the split covers "
                                + ", ".join(sorted(comps)))
        years.append(y)
    obs = []
    va = [(y.fiscal_year_end, y.valuation_allowance) for y in years if y.valuation_allowance is not None]
    if len(va) >= 2 and va[1][1]:
        chg = va[0][1] - va[1][1]
        obs.append(f"Valuation allowance moved {chg:+,.0f} ({chg / va[1][1]:+.1%}) to {va[0][1]:,.0f} - review the "
                   "positive/negative evidence and the four sources of taxable income (ASC 740-10-30-17 to 30-22)")
    utb = [(y.fiscal_year_end, y.unrecognized_tax_benefits) for y in years if y.unrecognized_tax_benefits is not None]
    if utb and years and years[0].income_tax_expense:
        obs.append(f"Unrecognized tax benefits of {utb[0][1]:,.0f} equal {utb[0][1] / years[0].income_tax_expense:.0%} "
                   "of a year's tax expense (ASC 740-10-25-6 recognition / 30-7 measurement)")
    return SecTaxProfile(company, source, as_of, years, obs)


# ------------------------------------------------------------------ IRS rates ---
# IRC 6621 underpayment rate for individuals (federal short-term rate + 3%). Dated table so callers
# can see which quarters are confirmed; refresh from irs.gov/payments/quarterly-interest-rates.
UNDERPAYMENT_RATES = {
    "2025Q1": 0.07, "2025Q2": 0.07, "2025Q3": 0.07, "2025Q4": 0.07,
    "2026Q1": 0.07, "2026Q2": 0.06, "2026Q3": 0.07, "2026Q4": 0.07,
}
UNDERPAYMENT_RATES_SOURCE = ("IRS quarterly interest rates (irs.gov/payments/quarterly-interest-rates); IR-2026-98 / "
                             "Rev. Rul. 2026-15 for Q4 2026. Checked 2026-11-26.")


def underpayment_rate(quarter: str, overrides: Optional[Dict[str, float]] = None) -> dict:
    """Rate for 'YYYYQn', with a live override (e.g. fetched from irs.gov) taking precedence."""
    if overrides and quarter in overrides:
        return {"quarter": quarter, "rate": overrides[quarter], "source": "caller-supplied (live)"}
    if quarter not in UNDERPAYMENT_RATES:
        raise ValueError(f"No bundled rate for {quarter}; fetch it from irs.gov and pass it as an override")
    return {"quarter": quarter, "rate": UNDERPAYMENT_RATES[quarter], "source": UNDERPAYMENT_RATES_SOURCE}
