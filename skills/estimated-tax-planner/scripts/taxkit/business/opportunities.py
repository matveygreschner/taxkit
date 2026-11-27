"""Business tax opportunity scanner.

``scan(profile)`` runs every check against a :class:`CompanyProfile` and returns
:class:`Opportunity` records sorted by estimated first-year federal tax savings.
Estimates are deliberately transparent: each opportunity lists the assumptions
behind its number, the actions to take, and the authority it rests on.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, List, Optional

from ..depreciation import personal_property_schedule, real_property_depreciation
from ..params import DEFAULT_YEAR, param
from ..rates import marginal_rate
from .bparams import bparam
from .entity import compare_entities, reasonable_comp_sweep


# ------------------------------------------------------------------ inputs --
@dataclass
class Asset:
    description: str
    cost: float
    recovery_class: float               # 3, 5, 7, 10, 15, 20, 27.5, 39
    acquired_after_jan19_2025: bool = True
    business_use_pct: float = 1.0
    used_in_manufacturing_building: bool = False   # deprecated: use CompanyProfile.building_used_in_production


@dataclass
class CompanyProfile:
    name: str = "Company"
    year: int = DEFAULT_YEAR
    entity_type: str = "s_corp"                 # sole_prop | partnership | s_corp | c_corp
    industry: str = ""
    sstb: bool = False                          # specified service trade or business (Sec. 199A)
    avg_gross_receipts_3yr: float = 0.0
    avg_gross_receipts_5yr: float | None = None   # Sec. 45F small-business test (defaults to the 3-yr figure)
    is_tax_shelter: bool = False                  # syndicate / tax shelter: no Sec. 448(c) small-business relief
    current_year_gross_receipts: float = 0.0
    years_with_receipts: int = 10
    net_income_before_owner_pay: float = 0.0    # profit before owner salary / guaranteed payments
    owner_salary: float = 0.0                   # W-2 to owner (S/C corp) or guaranteed payments (partnership)
    owner_filing_status: str = "MFJ"
    owner_other_income: float = 0.0
    owner_other_salt: float = 0.0               # owner's property + other state/local taxes
    num_owners: int = 1
    employees: int = 0
    non_owner_wages: float = 0.0
    ubia: float = 0.0
    state_income_tax_rate: float = 0.0
    state_has_ptet: bool = True
    uses_accrual_method: bool = False
    accounts_receivable: float = 0.0
    accounts_payable_and_accruals: float = 0.0
    # assets / depreciation
    assets: List[Asset] = field(default_factory=list)
    building_cost_placed_in_service: float = 0.0   # nonresidential/residential building (excl. land) this year
    building_is_residential: bool = False
    building_used_in_production: bool = False      # manufacturing/production use (Sec. 168(n))
    building_production_share: float = 1.0         # share of the building used in production
    building_original_use: bool = True             # False if bought used (168(n) has a narrow used-property rule)
    building_construction_began_after_jan19_2025: bool = True
    cost_seg_reclass_pct: float = 0.25             # typical share reclassified to 5/7/15-year
    # R&D
    domestic_research_expenses: float = 0.0
    unamortized_domestic_re_2022_2024: float = 0.0   # balance at the start of 2025
    re_baseline_amortization_this_year: float = 0.0  # amortization you'd take this year without the catch-up
    re_catchup_elected: str = "none"            # none | one_year (all in 2025) | two_year (half 2025, half 2026)
    elects_to_amortize_domestic_re: bool = False
    qualified_research_expenses: float = 0.0
    prior_3yr_qres: List[float] = field(default_factory=list)
    # financing
    business_interest_expense: float = 0.0
    business_interest_income: float = 0.0
    ebitda: float = 0.0
    depreciation_amortization: float = 0.0
    # people / benefits
    has_retirement_plan: bool = False
    nhce_count: int = 0
    plan_startup_costs: float = 5_000.0
    planned_employer_contribution_per_employee: float = 1_000.0
    employees_over_credit_wage_cap: int = 0        # employees with FICA wages over $105K (2025) / $110K (2026)
    hiring_new_employees: bool = False
    childcare_expenses: float = 0.0                # qualified childcare facility/provider expenditures
    childcare_referral_expenses: float = 0.0        # resource & referral expenditures (10%)
    paid_family_leave_wages: float = 0.0
    # owners' capital events
    qsbs_eligible_stock: bool = False
    qsbs_issued_after_jul4_2025: bool = True
    qsbs_basis: float = 0.0
    qsbs_expected_gain: float = 0.0
    qsbs_years_held_at_sale: float = 0.0
    qsbs_gross_assets_at_issuance: float = 0.0
    charitable_contributions: float = 0.0
    nol_carryforward: float = 0.0
    capital_gain_to_reinvest: float = 0.0
    gain_realization_date: str = ""                # YYYY-MM-DD
    qof_investment_date: str = ""                  # YYYY-MM-DD planned investment in the QOF
    oz_rural_fund: bool = False
    energy_projects_in_progress: bool = False
    discount_rate: float = 0.07
    method: str = "law"
    as_of: str = ""                                # YYYY-MM-DD the scan is run (defaults to today)

    @classmethod
    def from_dict(cls, d: dict) -> "CompanyProfile":
        import math
        if not isinstance(d, dict):
            raise ValueError("profile must be a JSON object")
        d = dict(d)
        known = set(cls.__dataclass_fields__)
        unknown = sorted(set(d) - known)
        if unknown:
            raise ValueError(f"unknown profile field(s): {', '.join(unknown)}")
        d["assets"] = [a if isinstance(a, Asset) else Asset(**a) for a in d.get("assets", [])]
        p = cls(**d)
        if p.entity_type not in ("sole_prop", "partnership", "s_corp", "c_corp"):
            raise ValueError("entity_type must be sole_prop, partnership, s_corp or c_corp")
        if not (math.isfinite(p.discount_rate) and -1 < p.discount_rate < 1):
            raise ValueError("discount_rate must be a finite decimal between -1 and 1 (e.g. 0.07)")
        for a in p.assets:
            if a.recovery_class not in (3, 5, 7, 10, 15, 20, 27.5, 39):
                raise ValueError(f"asset {a.description!r}: recovery_class must be 3, 5, 7, 10, 15, 20, 27.5 or 39")
            if a.cost < 0 or not 0 <= a.business_use_pct <= 1:
                raise ValueError(f"asset {a.description!r}: cost must be >= 0 and business_use_pct between 0 and 1")
        if p.num_owners < 1:
            raise ValueError("num_owners must be at least 1")
        return p


@dataclass
class Opportunity:
    id: str
    title: str
    category: str
    applies: bool
    est_savings: float = 0.0           # first-year federal tax reduction (or PV of timing benefit)
    savings_type: str = "permanent"    # permanent | timing (PV) | credit | refund | compliance
    summary: str = ""
    assumptions: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    authority: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    confidence: str = "medium"         # high | medium | low
    detail: dict = field(default_factory=dict)


# ----------------------------------------------------------------- helpers --
def _is_corp(p):
    return p.entity_type == "c_corp"


def _rate(p: CompanyProfile, extra_income: float = 0.0) -> float:
    """Marginal federal rate on business income: 21% for a C corp, else the owner's bracket
    (+ ~2.9% Medicare/SE is ignored here; the entity comparison models payroll taxes exactly)."""
    if _is_corp(p):
        return param("corp_rate", p.year)
    ti = _base_profit(p) / max(1, p.num_owners) + p.owner_other_income + extra_income
    ti -= p.owner_salary * 0.0765 if p.entity_type == "s_corp" else 0.0
    ti -= param("std_deduction", p.year, p.owner_filing_status)
    return marginal_rate(max(0.0, ti * 0.85), p.owner_filing_status, p.year)  # ~QBI-adjusted


def _baseline_depreciation(p: CompanyProfile) -> float:
    """Year-1 depreciation with no acceleration (MACRS half-year, building straight line). The profile's
    ``net_income_before_owner_pay`` is BEFORE depreciation on the assets listed in the profile."""
    d = 0.0
    for a in p.assets:
        if a.recovery_class in (27.5, 39):
            d += real_property_depreciation(a.cost, 1, a.recovery_class == 27.5, years=1)[0].depreciation
        else:
            d += personal_property_schedule(a.cost, int(a.recovery_class), "HY",
                                            business_use_pct=a.business_use_pct).first_year_total
    if p.building_cost_placed_in_service:
        d += real_property_depreciation(p.building_cost_placed_in_service, 1, p.building_is_residential,
                                        years=1)[0].depreciation
    return d


def _base_profit(p: CompanyProfile) -> float:
    return p.net_income_before_owner_pay - _baseline_depreciation(p)


def _tax_at(p: CompanyProfile, profit_before_owner_pay: float) -> float:
    """Total federal tax (entity + owner incl. payroll) for the current structure at a given profit."""
    if _is_corp(p):
        er = 0.0765 * min(p.owner_salary, param("ss_wage_base", p.year)) + 0.0145 * max(
            0.0, p.owner_salary - param("ss_wage_base", p.year)) if p.owner_salary else 0.0
        return param("corp_rate", p.year) * max(0.0, profit_before_owner_pay - p.owner_salary - er)
    ent = "sole_prop" if p.entity_type in ("sole_prop", "partnership") else "s_corp"
    per = max(1, p.num_owners)
    r = compare_entities(profit_before_owner_pay / per, p.owner_salary / per, p.owner_filing_status, p.year,
                         other_income=p.owner_other_income, other_employee_wages=p.non_owner_wages / per,
                         ubia=p.ubia / per, sstb=p.sstb, method=p.method, entities=[ent])[0]
    return (r.total_tax - (r.owner_state_tax or 0.0)) * per


def _deduction_value(p: CompanyProfile, amount: float, base: float | None = None) -> float:
    """Federal tax saved this year by an extra deduction, computed with the engine (so it reflects
    bracket changes, SE/FICA, QBI, and zero value once income is used up)."""
    b = _base_profit(p) if base is None else base
    return _tax_at(p, b) - _tax_at(p, b - amount)


def _as_of(p: CompanyProfile):
    import datetime
    if p.as_of:
        return datetime.date.fromisoformat(p.as_of)
    return datetime.date.today()


def _pv(cashflows: List[float], r: float) -> float:
    return sum(cf / (1 + r) ** t for t, cf in enumerate(cashflows))


def _small_business(p):
    return not p.is_tax_shelter and p.avg_gross_receipts_3yr <= bparam("gross_receipts_test", p.year)


# ------------------------------------------------------------------ checks --
def check_entity_choice(p: CompanyProfile) -> Opportunity:
    o = Opportunity("entity_choice", "Entity choice: compare sole prop / S corp / C corp", "Structure", False,
                    authority=["IRC 1, 11, 199A, 1361-1379, 1401", "OBBBA sec. 70105 (QBI permanent)"])
    if p.num_owners != 1 or p.net_income_before_owner_pay <= 0:
        o.summary = "Modeled for a single profitable owner; multi-owner comparisons need per-owner facts."
        return o
    salary = p.owner_salary or 0.4 * p.net_income_before_owner_pay
    res = compare_entities(p.net_income_before_owner_pay, salary, p.owner_filing_status, p.year,
                           other_income=p.owner_other_income, other_employee_wages=p.non_owner_wages, ubia=p.ubia,
                           sstb=p.sstb, state_rate=p.state_income_tax_rate, method=p.method)
    by = {r.entity: r for r in res}
    cur_key = "sole_prop" if p.entity_type in ("sole_prop", "partnership") else p.entity_type
    cur = by[cur_key]
    best = min(res, key=lambda r: r.total_tax)
    o.applies = best.entity != cur_key and cur.total_tax - best.total_tax > 1_000
    o.est_savings = round(max(0.0, cur.total_tax - best.total_tax), 2)
    o.detail = {r.entity: {"total_tax": r.total_tax, "after_tax_cash": r.after_tax_cash_to_owner,
                           "effective_rate": round(r.effective_rate, 4), "qbi_deduction": r.qbi_deduction}
                for r in res}
    o.summary = (f"Combined tax is lowest as a {best.entity.replace('_', ' ')} "
                 f"(${best.total_tax:,.0f} vs ${cur.total_tax:,.0f} as currently organized).")
    o.assumptions = [f"Single owner, profit before owner pay ${p.net_income_before_owner_pay:,.0f}",
                     f"S/C corp owner salary ${salary:,.0f}", "C corp distributes all after-tax profit as qualified dividends",
                     f"Flat illustrative state rate {p.state_income_tax_rate:.1%}"]
    o.actions = ["Model 3-5 year cash needs (C corp retention changes the answer)", "Check state franchise/PTET rules",
                 "If converting, consider Form 2553 timing and built-in gains (Sec. 1374)"]
    o.risks = ["Conversion costs, payroll compliance, state taxes and exit plans (QSBS, asset sale) can outweigh annual savings."]
    o.confidence = "medium"
    return o


def check_reasonable_comp(p: CompanyProfile) -> Opportunity:
    o = Opportunity("s_corp_salary", "S corp owner salary vs. distributions", "Compensation", False,
                    authority=["Rev. Rul. 74-44", "David E. Watson, P.C. v. U.S., 668 F.3d 1008 (8th Cir. 2012)",
                               "IRS: S corporation compensation and medical insurance issues (irs.gov)"])
    if p.entity_type != "s_corp" or p.net_income_before_owner_pay <= 0:
        return o
    sweep = reasonable_comp_sweep(p.net_income_before_owner_pay, p.owner_filing_status, p.year,
                                  other_income=p.owner_other_income, other_employee_wages=p.non_owner_wages,
                                  ubia=p.ubia, sstb=p.sstb, state_rate=p.state_income_tax_rate, method=p.method)
    cur = compare_entities(p.net_income_before_owner_pay, p.owner_salary, p.owner_filing_status, p.year,
                           other_income=p.owner_other_income, other_employee_wages=p.non_owner_wages, ubia=p.ubia,
                           sstb=p.sstb, state_rate=p.state_income_tax_rate, method=p.method, entities=["s_corp"])[0]
    o.detail = {"current_salary": p.owner_salary, "current_total_tax": cur.total_tax, "sweep": sweep}
    o.applies = True
    o.savings_type = "permanent"
    o.est_savings = 0.0
    o.summary = ("Salary level drives FICA and the QBI wage limit. Document a reasonable salary "
                 "(comparable pay for the owner's duties); the sweep shows the tax at each level.")
    o.actions = ["Benchmark salary with comp surveys / BLS data for the owner's role and hours",
                 "Keep a written reasonable-compensation memo in the corporate records"]
    o.risks = ["Salary set below a reasonable level can be recharacterized as wages with penalties and interest."]
    o.confidence = "high"
    return o


def _timing_pv(p: CompanyProfile, fast: List[float], slow: List[float]) -> tuple:
    """PV of moving deductions from schedule ``slow`` to ``fast`` (each a list of yearly deductions),
    valuing each year's deduction with the engine at current income. Returns (pv_gain, year1_tax_change)."""
    n = max(len(fast), len(slow))
    fast = fast + [0.0] * (n - len(fast))
    slow = slow + [0.0] * (n - len(slow))
    r = p.discount_rate
    val = [(_deduction_value(p, f) - _deduction_value(p, s_)) / (1 + r) ** t for t, (f, s_) in enumerate(zip(fast, slow))]
    return sum(val), val[0] if val else 0.0


def check_depreciation(p: CompanyProfile) -> Opportunity:
    o = Opportunity("bonus_179", "100% bonus depreciation / Sec. 179 on new equipment", "Cost recovery", False,
                    savings_type="timing (PV)",
                    authority=["IRC 168(k) as amended by OBBBA sec. 70301 (100% for property acquired after 1/19/2025)",
                               "Notice 2026-11", "IRC 179 (OBBBA sec. 70306)"])
    if not p.assets:
        return o
    base_first = acc_first = 0.0
    fast_all, slow_all, rows = [], [], []
    for a in p.assets:
        if a.recovery_class in (27.5, 39):
            continue
        cls = int(a.recovery_class)
        macrs = personal_property_schedule(a.cost, cls, "HY", business_use_pct=a.business_use_pct)
        bonus_pct = 1.0 if a.acquired_after_jan19_2025 else bparam("bonus_pre_jan20_2025", p.year)
        fast = personal_property_schedule(a.cost, cls, "HY", bonus_pct=bonus_pct if a.business_use_pct > 0.5 else 0,
                                          business_use_pct=a.business_use_pct)
        slow_d = [x.depreciation for x in macrs.schedule]
        fast_d = [fast.bonus + (fast.schedule[0].depreciation if fast.schedule else 0)] + \
                 [x.depreciation for x in fast.schedule[1:]]
        for lst, src in ((fast_all, fast_d), (slow_all, slow_d)):
            for i, v in enumerate(src):
                if i < len(lst):
                    lst[i] += v
                else:
                    lst.append(v)
        base_first += macrs.first_year_total
        acc_first += fast.first_year_total
        rows.append({"asset": a.description, "cost": a.cost, "class": cls, "bonus_pct": bonus_pct,
                     "first_year_macrs": macrs.first_year_total, "first_year_bonus": fast.first_year_total})
    if not rows:
        return o
    pv_gain, yr1 = _timing_pv(p, fast_all, slow_all)
    o.applies = acc_first > base_first      # 100% bonus is the default, so it always deserves a decision
    o.est_savings = round(max(0.0, pv_gain), 2)
    o.detail = {"assets": rows, "first_year_deduction_macrs": round(base_first, 2),
                "first_year_deduction_bonus": round(acc_first, 2), "first_year_tax_reduction": round(yr1, 2)}
    o.summary = (f"Expensing moves ${acc_first - base_first:,.0f} of deductions into year 1 "
                 f"(~${yr1:,.0f} less tax now; PV benefit ${pv_gain:,.0f} at {p.discount_rate:.0%}).")
    if pv_gain <= 0:
        o.summary = (f"100% bonus would put ${acc_first - base_first:,.0f} of extra deductions into year 1, but this "
                     f"year's income can't absorb them, so regular MACRS is worth ${-pv_gain:,.0f} more in PV. "
                     "Elect out of bonus by class and use Sec. 179 for a targeted amount instead.")
    o.assumptions = ["Each year's deduction valued with the full engine at current income", "Half-year convention",
                     f"Discount rate {p.discount_rate:.0%}"]
    o.actions = ["Confirm acquisition dates (binding contract date) for each asset",
                 "Choose 100% bonus vs Sec. 179 (179 is limited to business income but can be elected asset-by-asset; "
                 "many states decouple from bonus)",
                 "Consider electing out by class (any year) if you expect higher future rates or have expiring NOLs; "
                 "the 40% election is available only on the first tax year ending after 1/19/2025",
                 "Heavy SUVs: Sec. 179 capped at $32,000 (2026)"]
    o.risks = ["Recapture as ordinary income on sale (Sec. 1245)", "State conformity varies",
               "Valued alone - see the deduction-capacity check for the combined effect"]
    o.confidence = "high"
    return o


def check_cost_segregation(p: CompanyProfile) -> Opportunity:
    o = Opportunity("cost_seg", "Cost segregation study on building", "Cost recovery", False, savings_type="timing (PV)",
                    authority=["IRC 168(k)", "Hospital Corp. of America, 109 T.C. 21 (1997)", "IRS Cost Segregation Audit Techniques Guide"])
    b = p.building_cost_placed_in_service - _qpp_amount(p)
    if b < 500_000:
        o.summary = "Usually worthwhile only for buildings above roughly $500K-$1M of depreciable basis."
        return o
    r = p.discount_rate
    life = 27.5 if p.building_is_residential else 39
    years = 40
    base = real_property_depreciation(b, 1, p.building_is_residential, years=years)
    re = b * p.cost_seg_reclass_pct
    seg_rest = real_property_depreciation(b - re, 1, p.building_is_residential, years=years)
    gain, _ = _timing_pv(p, [x.depreciation + (re if i == 0 else 0) for i, x in enumerate(seg_rest)],
                         [x.depreciation for x in base])
    rate = _rate(p)
    o.applies = gain > 0
    o.est_savings = round(max(0.0, gain), 2)
    o.detail = {"building_basis": b, "reclassified": re, "year1_without": round(base[0].depreciation, 2),
                "year1_with": round(seg_rest[0].depreciation + re, 2), "recovery_period": life}
    o.summary = (f"Reclassifying ~{p.cost_seg_reclass_pct:.0%} (${re:,.0f}) to 5/7/15-year property makes it eligible "
                 f"for 100% bonus: year-1 deduction ${seg_rest[0].depreciation + re:,.0f} vs ${base[0].depreciation:,.0f}.")
    o.assumptions = [f"{p.cost_seg_reclass_pct:.0%} reclassification (typical 15-40%)", "Placed in service in January",
                     "Deductions valued with the full engine at current income", f"Discount rate {r:.0%}"]
    if any(a.recovery_class in (27.5, 39) for a in p.assets):
        o.risks.append("A 27.5/39-year asset is also listed in `assets` - enter each building once (in "
                       "building_cost_placed_in_service) so its basis isn't counted twice")
    o.actions = ["Engineer-based study (cost ~$5K-$15K)", "For buildings placed in service earlier, catch up with Form 3115 (DCN 7)"]
    o.risks = ["Recapture of reclassified property at ordinary rates on sale", "Passive activity limits for rentals"]
    return o


def _qpp_amount(p: CompanyProfile) -> float:
    if not (p.building_used_in_production and p.building_cost_placed_in_service):
        return 0.0
    if not p.building_construction_began_after_jan19_2025:
        return 0.0
    return p.building_cost_placed_in_service * p.building_production_share


def check_qpp(p: CompanyProfile) -> Opportunity:
    o = Opportunity("qpp_168n", "100% expensing of manufacturing buildings (qualified production property)",
                    "Cost recovery", False, savings_type="timing (PV)",
                    authority=["IRC 168(n) as added by OBBBA sec. 70307", "Notice 2026-16"])
    amt = _qpp_amount(p)
    if not amt:
        if p.building_used_in_production and not p.building_construction_began_after_jan19_2025:
            o.summary = "Construction must begin after 1/19/2025 for Sec. 168(n)."
        return o
    life = 27.5 if p.building_is_residential else 39
    sl1 = real_property_depreciation(amt, 1, False, years=1)[0].depreciation
    now = _deduction_value(p, amt - sl1)
    later = now * (1 - 1 / (1 + p.discount_rate) ** (life / 2))
    o.applies = True
    o.est_savings = round(later, 2)
    o.detail = {"qualifying_amount": round(amt, 2), "first_year_tax_reduction": round(now, 2)}
    o.summary = (f"The production portion of the building (${amt:,.0f}) may be fully expensed instead of "
                 f"depreciated over 39 years: ~${now:,.0f} less tax this year.")
    o.assumptions = ["Construction began after 1/19/2025 and before 1/1/2029; placed in service after 7/4/2025 and "
                     "before 1/1/2031", "Value = PV of the timing benefit (midpoint of the recovery period)"]
    if not p.building_original_use:
        o.confidence = "low"
        o.risks.append("Bought used: qualifies only if it wasn't used in a production activity between 1/1/2021 and "
                       "5/12/2025 and was acquired in the 2025-2029 window - confirm with the seller's history")
    o.actions = ["Elect on the return and designate the production portion (exclude offices, R&D, storage for sale)",
                 "Plan for recapture if production use stops within 10 years (confirm against Sec. 168(n) and Notice 2026-16)"]
    o.risks.append("Recapture if production use stops; check state conformity")
    return o


def check_research_expensing(p: CompanyProfile) -> Opportunity:
    o = Opportunity("rd_174a", "Domestic R&E: Sec. 174A expensing and 2022-2024 catch-up", "R&D", False,
                    savings_type="timing (PV)",
                    authority=["IRC 174A as added by OBBBA sec. 70302", "Rev. Proc. 2025-28"])
    rate = _rate(p)
    cur, unam = p.domestic_research_expenses, p.unamortized_domestic_re_2022_2024
    if not (cur or unam):
        return o
    sav, notes = 0.0, []
    if cur and p.elects_to_amortize_domestic_re:
        sav += cur * rate * 0.9
        notes.append(f"Deducting this year's ${cur:,.0f} instead of amortizing it over 60 months")
    if unam:
        base_amort = p.re_baseline_amortization_this_year
        if p.year == 2025:
            inst = unam / 2 if p.re_catchup_elected == "two_year" else unam
            sav += _deduction_value(p, max(0.0, inst - base_amort))
            notes.append(f"Catch-up: deduct ${inst:,.0f} of the ${unam:,.0f} unamortized 2022-2024 domestic R&E in 2025 "
                         + ("(half now, half in 2026)" if p.re_catchup_elected == "two_year" else
                            "(or elect half in 2025 and half in 2026)") + "; value is net of normal amortization")
        elif p.re_catchup_elected == "two_year" and p.year == 2026:
            inst = unam / 2
            sav += _deduction_value(p, max(0.0, inst - base_amort))
            notes.append(f"Second half of the two-year catch-up (${inst:,.0f}) must be deducted in 2026")
        elif p.year >= 2026 and p.re_catchup_elected == "none":
            notes.append(f"The ${unam:,.0f} 2022-2024 balance keeps amortizing on its original schedule - the "
                         "catch-up election could only be made on the 2025 return (check that it was considered)")
    o.applies = sav > 0
    o.est_savings = round(sav, 2)
    o.summary = ("Domestic research costs are deductible when paid for tax years beginning after 2024 (the default). "
                 + ("; ".join(notes) + "." if notes else "No catch-up or capitalization issue found."))
    o.actions = ["Confirm domestic R&E is deducted (not amortized) unless amortizing helps credits, NOLs or Sec. 163(j)",
                 "Catch-up for unamortized 2022-2024 domestic amounts: elect all in 2025 or ratably over 2025-2026 "
                 "(statement in lieu of Form 3115); if two-year, take the 2026 half",
                 "Note: the small-business retroactive amended-return election closed July 6, 2026"]
    o.assumptions = [f"Marginal rate {rate:.0%}", "Value shown = tax on the deduction accelerated into this year"]
    o.risks = ["Foreign research remains 15-year amortization under Sec. 174",
               "Sec. 174A deduction is reduced by the research credit unless the Sec. 280C(c) election is made"]
    o.confidence = "high"
    return o


def check_research_credit(p: CompanyProfile) -> Opportunity:
    o = Opportunity("rd_credit", "Research credit (Sec. 41, ASC method)", "R&D", False, savings_type="credit",
                    authority=["IRC 41(c)(4)", "IRC 41(h) payroll offset", "IRC 280C(c)"])
    q = p.qualified_research_expenses
    if q <= 0:
        return o
    prior = p.prior_3yr_qres
    if len(prior) < 3 or min(prior) <= 0:
        credit = bparam("rd_asc_startup_rate", p.year) * q
        basis = "6% of current QREs (no QREs in one of the 3 prior years)"
    else:
        credit = bparam("rd_asc_rate", p.year) * max(0.0, q - 0.5 * sum(prior) / 3)
        basis = "14% of QREs over 50% of the prior 3-year average"
    reduced = credit * (1 - param("corp_rate", p.year))   # Sec. 280C(c)(2): reduced by the 21% rate for all taxpayers
    qsb = p.current_year_gross_receipts < bparam("rd_qsb_receipts", p.year) and p.years_with_receipts <= 5
    o.applies = True
    o.est_savings = round(reduced, 2)
    o.detail = {"gross_credit": round(credit, 2), "after_280c_reduced_credit": round(reduced, 2),
                "payroll_offset_eligible": qsb, "payroll_offset_max": bparam("rd_payroll_offset_max", p.year)}
    o.summary = f"Estimated credit ${credit:,.0f} ({basis}); ${reduced:,.0f} (79%) after the Sec. 280C reduced-credit election."
    if qsb:
        o.summary += " As a qualified small business, up to $500K/yr can offset payroll taxes even without income tax."
    o.actions = ["Document the four-part test by project (wages, supplies, 65% of contract research)",
                 "Elect the ASC and the reduced credit on a timely filed original return (Form 6765)",
                 "Payroll offset (if eligible): elect on a timely original Form 6765, claim on Form 8974 with Form 941; max 5 years"]
    o.risks = ["Substantiation is the main audit risk; Form 6765 Section G project reporting"]
    o.confidence = "medium"
    return o


def check_interest_limit(p: CompanyProfile) -> Opportunity:
    o = Opportunity("interest_163j", "Business interest limitation (Sec. 163(j))", "Financing", False,
                    authority=["IRC 163(j) (EBITDA-based ATI restored by OBBBA sec. 70303)"])
    i = p.business_interest_expense
    if i <= 0:
        return o
    if _small_business(p):
        o.applies = False
        o.summary = "Exempt: average gross receipts are under the Sec. 448(c) small business threshold."
        return o
    ebitda = p.ebitda
    ebit = ebitda - p.depreciation_amortization
    lim_now = p.business_interest_income + bparam("interest_limit_pct", p.year) * max(0.0, ebitda)
    lim_old = p.business_interest_income + bparam("interest_limit_pct", p.year) * max(0.0, ebit)
    dis_now, dis_old = max(0.0, i - lim_now), max(0.0, i - lim_old)
    rate = _rate(p)
    o.applies = True
    o.est_savings = round((dis_old - dis_now) * rate, 2)
    o.detail = {"limit_ebitda": round(lim_now, 2), "limit_ebit": round(lim_old, 2),
                "disallowed_now": round(dis_now, 2), "disallowed_under_2022_2024_rule": round(dis_old, 2)}
    o.summary = (f"Deductible interest limit ${lim_now:,.0f} (30% of EBITDA); ${dis_now:,.0f} carried forward. "
                 f"The EBITDA rule frees ${dis_old - dis_now:,.0f} vs the 2022-2024 EBIT rule.")
    o.actions = ["Use carried-forward interest from prior years first",
                 "Real property businesses: consider the electing real property trade or business election (ADS required, so no bonus)",
                 "From 2026 the limit applies before most interest capitalization - capitalizing interest no longer avoids it"]
    o.confidence = "medium"
    return o


def check_cash_method(p: CompanyProfile) -> Opportunity:
    o = Opportunity("cash_method", "Switch to the cash method (small business)", "Accounting methods", False,
                    savings_type="timing (PV)", authority=["IRC 448(c), 471(c), 263A(i)", "Rev. Proc. 2015-13", "Rev. Proc. 2025-23 (method changes list)"])
    if not p.uses_accrual_method or not _small_business(p):
        return o
    net = p.accounts_receivable - p.accounts_payable_and_accruals
    if net <= 0:
        return o
    rate = _rate(p)
    o.applies = True
    deferred = _deduction_value(p, net)
    horizon = 10
    o.est_savings = round(deferred * (1 - 1 / (1 + p.discount_rate) ** horizon), 2)
    o.detail = {"favorable_481a_adjustment": net, "tax_deferred": round(deferred, 2),
                "pv_horizon_years": horizon}
    o.summary = (f"With receipts under ${bparam('gross_receipts_test', p.year):,.0f}, the cash method defers tax on "
                 f"~${net:,.0f} of net receivables (${deferred:,.0f} of tax deferred, as long as the business "
                 f"keeps that level of receivables).")
    o.assumptions = [f"Value = PV of deferring the tax for {horizon} years at {p.discount_rate:.0%} (the deferral "
                     "lasts while receivables stay at this level)", "Deduction valued with the engine at current income"]
    o.actions = ["File Form 3115 (automatic change); a favorable Sec. 481(a) adjustment is taken in the year of change",
                 "Consider treating inventory as non-incidental materials (Sec. 471(c)) at the same time"]
    o.risks = ["Financial statements (lenders) may still require accrual GAAP books"]
    return o


def check_ptet(p: CompanyProfile) -> Opportunity:
    o = Opportunity("ptet", "Pass-through entity tax (PTET) election", "State & local", False,
                    authority=["IRS Notice 2020-75", "OBBBA (no PTET limitation enacted)", "State PTET statutes"])
    if p.entity_type not in ("s_corp", "partnership") or not p.state_has_ptet or p.state_income_tax_rate <= 0:
        return o
    from ..form1040 import Return1040, compute_return
    share = (p.net_income_before_owner_pay - p.owner_salary) / max(1, p.num_owners)
    if share <= 0:
        return o
    state_tax_biz = share * p.state_income_tax_rate
    st = p.owner_filing_status
    common = dict(year=p.year, status=st, wages=p.owner_salary / max(1, p.num_owners),
                  other_income=p.owner_other_income, method=p.method)
    # K-1 income enters as other_income; add it separately so the two runs differ only by PTET.
    without = compute_return(Return1040(**{**common, "other_income": common["other_income"] + share}, other_qbi=share,
                                        itemized={"state_local_taxes": p.owner_other_salt + state_tax_biz
                                                  + p.state_income_tax_rate * p.owner_salary / max(1, p.num_owners)}))
    with_ = compute_return(Return1040(**{**common, "other_income": common["other_income"] + share - state_tax_biz},
                                      other_qbi=share - state_tax_biz,
                                      itemized={"state_local_taxes": p.owner_other_salt
                                                + p.state_income_tax_rate * p.owner_salary / max(1, p.num_owners)}))
    sav = without.total_tax - with_.total_tax
    o.applies = sav > 0
    o.est_savings = round(sav * max(1, p.num_owners), 2)
    o.detail = {"entity_level_state_tax": round(state_tax_biz * max(1, p.num_owners), 2),
                "owner_tax_without": without.total_tax, "owner_tax_with": with_.total_tax}
    o.summary = (f"Paying ~${state_tax_biz * max(1, p.num_owners):,.0f} of state tax at the entity level makes it "
                 f"deductible above the SALT cap; federal savings ~${sav * max(1, p.num_owners):,.0f}.")
    o.assumptions = ["Owner's federal tax recomputed with and without the election (SALT cap and the "
                     "PTET's reduction of QBI both applied)",
                     "State gives owners a full credit for PTET paid"]
    o.actions = ["Make the state election by its deadline (often before year-end or with the return)",
                 "Pay estimates at the entity level before 12/31 to deduct in the current year"]
    o.risks = ["Some states don't credit nonresident owners; QBI is reduced by the PTET deduction"]
    o.confidence = "medium"
    return o


def check_qbi(p: CompanyProfile) -> Opportunity:
    o = Opportunity("qbi_planning", "Qualified business income deduction planning (Sec. 199A)", "Structure", False,
                    authority=["IRC 199A (made permanent by OBBBA sec. 70105)"])
    if _is_corp(p) or p.net_income_before_owner_pay <= 0:
        return o
    from ..individual import qbi_deduction_full
    qbi = (p.net_income_before_owner_pay - (p.owner_salary if p.entity_type == "s_corp" else 0)) / max(1, p.num_owners)
    ti = qbi + p.owner_other_income + (p.owner_salary if p.entity_type == "s_corp" else 0) - param(
        "std_deduction", p.year, p.owner_filing_status)
    n = max(1, p.num_owners)   # QBI, W-2 wages and UBIA are allocated by ownership share (Reg. 1.199A-2)
    w2 = (p.non_owner_wages + (p.owner_salary if p.entity_type == "s_corp" else 0)) / n
    d = qbi_deduction_full(qbi, w2, p.ubia / n, ti, 0.0, p.owner_filing_status, p.sstb, p.year)
    thr = param("qbi_threshold", p.year, p.owner_filing_status)
    lost = max(0.0, 0.2 * qbi - d.deduction)
    o.applies = lost > 0 or ti > thr
    o.est_savings = round(lost * marginal_rate(max(0.0, ti), p.owner_filing_status, p.year), 2)
    o.detail = {"qbi": round(qbi, 2), "deduction": d.deduction, "full_20pct": round(0.2 * qbi, 2),
                "wage_limit": d.wage_limit, "threshold": thr, "taxable_income_est": round(ti, 2)}
    o.summary = (f"QBI deduction ${d.deduction:,.0f} of a possible ${0.2 * qbi:,.0f}. " +
                 ("Limited by the W-2 wage / SSTB rules - " if lost > 0 else "") +
                 f"taxable income ~${ti:,.0f} vs threshold ${thr:,.0f}.")
    o.actions = ["Keep taxable income under the threshold with retirement contributions or timing of deductions",
                 "Raise W-2 wages (S corp salary or hiring employees vs contractors) if the wage limit binds",
                 "Aggregate related businesses (Reg. 1.199A-4) to share wages"]
    return o


def check_retirement_plan(p: CompanyProfile) -> Opportunity:
    o = Opportunity("retirement_plan", "Owner 401(k)/SEP contributions and plan startup credits", "Benefits", False,
                    authority=["IRC 401(k), 402(g), 404, 415(c)", "IRC 45E, 45T (SECURE 2.0)",
                               "Reg. 1.401(k)-3 (safe harbor notice and timing)"])
    if p.net_income_before_owner_pay <= 0:
        return o
    y = p.year
    if p.entity_type in ("s_corp", "c_corp"):
        comp = p.owner_salary
        employer = 0.25 * comp
    else:
        net_se = max(0.0, _base_profit(p)) * 0.9235
        comp = net_se * 0.9235                     # earned income net of 1/2 SE tax (approx.)
        employer = 0.20 * comp
    deferral = min(param("k401_limit", y), comp)
    owner_total = min(param("dc_limit", y), comp, deferral + employer)   # Sec. 415(c): 100% of compensation
    owner_sav = _deduction_value(p, owner_total) if not _is_corp(p) else owner_total * _rate(p)
    credit = employee_cost = 0.0
    notes = []
    if not p.has_retirement_plan and 0 < p.employees <= 100:
        cap = max(500, min(bparam("nhce_credit_per", y) * max(1, p.nhce_count), bparam("startup_plan_credit_max", y)))
        startup_rate = bparam("plan_credit_rate_small", y) if p.employees <= 50 else 0.5
        startup = min(cap, startup_rate * p.plan_startup_costs)
        contrib_rate = 1.0 if p.employees <= 50 else max(0.0, 1.0 - 0.02 * (p.employees - 50))
        per_ee = min(bparam("employer_contrib_credit_per_ee", y), p.planned_employer_contribution_per_employee)
        avg_wage = p.non_owner_wages / p.employees if p.employees else 0
        eligible_ees = max(0, p.employees - p.employees_over_credit_wage_cap)   # FICA-wage cap applied per employee
        del avg_wage
        credit = startup + bparam("auto_enroll_credit", y) + contrib_rate * per_ee * eligible_ees
        # Safe-harbor design: 3% nonelective contribution for non-owner employees (a real cost).
        employee_cost = 0.03 * p.non_owner_wages
    if p.employees and not p.has_retirement_plan:
        when = _as_of(p)
        if when.year == y and when.month >= 10:
            notes.append("It is after Oct 1, so a new safe-harbor 401(k) can't cover this year's deferrals; set it up "
                         "for next year now. A SEP, or employer contributions to a plan adopted by the return due "
                         "date, can still count for this year.")
    after_tax_cost = employee_cost * (1 - _rate(p))
    net = owner_sav + credit - after_tax_cost
    o.applies = owner_sav > 0
    o.est_savings = round(net, 2)
    o.detail = {"max_owner_contribution": round(owner_total, 2), "owner_tax_saved": round(owner_sav, 2),
                "credits_year1_est": round(credit, 2), "employee_safe_harbor_cost": round(employee_cost, 2),
                "employee_cost_after_tax": round(after_tax_cost, 2)}
    o.summary = (f"Owner can shelter up to ~${owner_total:,.0f} (${owner_sav:,.0f} of tax)"
                 + (f"; plan credits ~${credit:,.0f}/yr for up to 3 years, less ~${after_tax_cost:,.0f} after-tax "
                    f"cost of a 3% safe-harbor contribution for employees" if credit else "") + ". "
                 + " ".join(notes))
    o.assumptions = ["Deferral saves tax now; withdrawals are taxed later",
                     f"Plan startup costs ${p.plan_startup_costs:,.0f}; employer credit contribution "
                     f"${p.planned_employer_contribution_per_employee:,.0f}/employee",
                     "Employee cost assumes a 3% safe-harbor nonelective contribution"]
    o.actions = ["No employees: solo 401(k) or SEP. With employees: safe-harbor 401(k) (adopt by Oct 1 for the year)",
                 "Credits: Sec. 45E startup (3 yrs), employer contribution credit (100% yrs 1-2, then 75/50/25%), "
                 "Sec. 45T auto-enroll $500"]
    o.savings_type = "credit" if credit else "timing (PV)"
    o.risks = ["Employee contributions are a real cost; nondiscrimination testing applies without a safe harbor"]
    return o


def check_childcare(p: CompanyProfile) -> Opportunity:
    o = Opportunity("childcare_45f", "Employer-provided childcare credit (Sec. 45F)", "Credits", False, savings_type="credit",
                    authority=["IRC 45F as amended by OBBBA sec. 70401 (2026+)"])
    if p.childcare_expenses <= 0 and p.childcare_referral_expenses <= 0:
        return o
    avg5 = p.avg_gross_receipts_3yr if p.avg_gross_receipts_5yr is None else p.avg_gross_receipts_5yr
    small = p.year >= 2026 and not p.is_tax_shelter and avg5 <= bparam("gross_receipts_test", p.year)
    rate = bparam("childcare_credit_rate_small" if small else "childcare_credit_rate", p.year)
    mx = bparam("childcare_credit_max_small" if small else "childcare_credit_max", p.year)
    c = min(mx, rate * p.childcare_expenses + 0.10 * p.childcare_referral_expenses)
    if p.avg_gross_receipts_5yr is None and p.year >= 2026:
        o.assumptions.append("Small-business test uses the 3-year average; the statute uses the 5-year average")
    o.applies = True
    o.est_savings = round(c, 2)
    o.summary = f"{rate:.0%} of qualified childcare costs, up to ${mx:,.0f}: ~${c:,.0f}."
    o.actions = ["Track qualified childcare facility / provider payments; resource-and-referral costs earn 10%"]
    return o


def check_paid_leave(p: CompanyProfile) -> Opportunity:
    o = Opportunity("paid_leave_45s", "Paid family & medical leave credit (Sec. 45S)", "Credits", False, savings_type="credit",
                    authority=["IRC 45S (made permanent and expanded by OBBBA sec. 70304)", "IRS guidance on the 45S expansion (2026)"])
    if p.paid_family_leave_wages <= 0:
        return o
    c = 0.125 * p.paid_family_leave_wages
    o.applies = True
    o.est_savings = round(c, 2)
    o.summary = f"12.5%-25% of wages paid during qualifying leave (estimate at 12.5%): ~${c:,.0f}."
    o.actions = ["Written policy: at least 2 weeks paid leave at >= 50% of normal wages for qualifying employees",
                 "From 2026 the credit can be based on premiums for paid-leave insurance instead of wages"]
    o.confidence = "low"
    return o


def check_qsbs(p: CompanyProfile) -> Opportunity:
    o = Opportunity("qsbs_1202", "Qualified small business stock exclusion (Sec. 1202)", "Exit planning", False,
                    authority=["IRC 1202 as amended by OBBBA sec. 70431"])
    if not _is_corp(p) or not p.qsbs_eligible_stock or p.qsbs_expected_gain <= 0:
        if p.entity_type != "c_corp" and p.qsbs_expected_gain > 0:
            o.summary = "QSBS needs C corporation stock acquired at original issuance."
        return o
    new = p.qsbs_issued_after_jul4_2025
    assets_lim = bparam("qsbs_assets" if new else "qsbs_assets_old", p.year)
    if p.qsbs_gross_assets_at_issuance > assets_lim:
        o.summary = f"Gross assets at issuance exceed ${assets_lim:,.0f}; not eligible."
        return o
    yrs = p.qsbs_years_held_at_sale
    if new:
        pct = 1.0 if yrs >= 5 else 0.75 if yrs >= 4 else 0.5 if yrs >= 3 else 0.0
    else:
        pct = 1.0 if yrs >= 5 else 0.0
    cap = max(bparam("qsbs_cap" if new else "qsbs_cap_old", p.year), 10 * p.qsbs_basis)
    eligible = min(p.qsbs_expected_gain, cap)
    excluded = eligible * pct
    tax_without = p.qsbs_expected_gain * 0.238
    tax_with = (eligible - excluded) * (0.28 + 0.038) * (1 if pct < 1 else 0) + (p.qsbs_expected_gain - eligible) * 0.238
    o.applies = pct > 0
    o.est_savings = round(max(0.0, tax_without - tax_with), 2)
    o.savings_type = "permanent"
    o.detail = {"exclusion_pct": pct, "per_issuer_cap": cap, "excluded_gain": round(excluded, 2)}
    o.summary = (f"Holding {yrs:g} years excludes {pct:.0%} of up to ${cap:,.0f} of gain: ${excluded:,.0f} excluded."
                 if pct else "Hold at least 3 years (post-7/4/2025 stock) or 5 years (earlier stock) to qualify.")
    o.actions = ["Confirm active business (80% assets) and not an excluded service business",
                 "Keep issuance-date gross asset records; consider gifting shares to stack the per-taxpayer cap"]
    o.risks = ["Partial-exclusion gain is taxed at 28% plus NIIT; AMT treatment of the 50%/75% tiers should be confirmed",
               "Redemptions around issuance can disqualify stock", "Stock issued on or before 7/4/2025 keeps the old 5-year / $10M / $50M rules"]
    return o


def check_charity_corp(p: CompanyProfile) -> Opportunity:
    o = Opportunity("corp_charity_timing", "Corporate charitable giving: 1% floor from 2026", "Timing", False,
                    authority=["IRC 170(b)(2) as amended by OBBBA sec. 70426"])
    if not _is_corp(p) or p.charitable_contributions <= 0:
        return o
    ti = p.net_income_before_owner_pay - p.owner_salary
    floor = 0.01 * max(0.0, ti)
    lost = min(p.charitable_contributions, floor)
    o.applies = p.year >= 2026
    o.est_savings = round(lost * param("corp_rate", p.year), 2) if p.year >= 2026 else 0.0
    o.summary = (f"From 2026 the first 1% of taxable income (~${floor:,.0f}) of corporate gifts is not deductible; "
                 f"bunching gifts into alternate years recovers ~${o.est_savings:,.0f}.")
    o.actions = ["Bunch two years of giving into one year, or fund a donor-advised fund in a single year"]
    return o


def check_compliance(p: CompanyProfile) -> Opportunity:
    o = Opportunity("compliance_2026", "2026 information-reporting and safe-harbor housekeeping", "Compliance", True,
                    savings_type="compliance",
                    authority=["OBBBA sec. 70432-70433 (1099-K / 1099-NEC thresholds)", "Reg. 1.263(a)-1(f) de minimis"])
    o.summary = ("1099-NEC/MISC threshold rises to $2,000 for payments after 2025 (1099-K is back to $20,000 and 200 "
                 "transactions). Adopt the de minimis safe harbor ($2,500 per item, $5,000 with an AFS) to expense small purchases"
                 + ("; buildings with basis <= $1M may also qualify for the small taxpayer safe harbor." if
                    p.avg_gross_receipts_3yr <= bparam("small_bldg_receipts", p.year) else "."))
    o.actions = ["Update AP vendor-reporting thresholds", "Attach the de minimis election statement to the return each year"]
    o.confidence = "high"
    return o


def accelerated_deductions(p: CompanyProfile) -> dict:
    """Extra first-year deductions (beyond baseline depreciation) each acceleration item would add."""
    out = {}
    dep = check_depreciation(p)
    if dep.applies:
        out["bonus_179"] = dep.detail["first_year_deduction_bonus"] - dep.detail["first_year_deduction_macrs"]
    cs = check_cost_segregation(p)
    if cs.applies:
        out["cost_seg"] = cs.detail["year1_with"] - cs.detail["year1_without"]
    q = _qpp_amount(p)
    if q:
        out["qpp_168n"] = q - real_property_depreciation(q, 1, False, years=1)[0].depreciation
    if p.uses_accrual_method and _small_business(p):
        net = p.accounts_receivable - p.accounts_payable_and_accruals
        if net > 0:
            out["cash_method"] = net
    return out


def check_deduction_capacity(p: CompanyProfile) -> Opportunity:
    o = Opportunity("deduction_capacity", "Right-size this year's accelerated deductions", "Timing", False,
                    savings_type="timing (PV)",
                    authority=["IRC 168(k)(7) (elect out by class)", "IRC 179 (elect asset by asset, income-limited)",
                               "IRC 172 (80% NOL limit)", "IRC 461(l)", "IRC 1366(d) (S corp basis limit)"])
    items = accelerated_deductions(p)
    extra = sum(items.values())
    if extra <= 0 or p.net_income_before_owner_pay <= 0:
        return o
    base = _base_profit(p)
    r = p.discount_rate
    t0 = _tax_at(p, base)

    spread = 5   # deferred deductions recovered evenly over the next 5 years (a proxy for MACRS lives)
    cache = {}

    def saved(d):
        k = round(d, 2)
        if k not in cache:
            cache[k] = t0 - _tax_at(p, base - d)
        return cache[k]

    steps = 40
    grid = [extra * i / steps for i in range(steps + 1)]
    top = saved(extra)
    capacity = next(d for d in grid if saved(d) >= top - 1)   # deduction that uses up this year's tax

    def pv(d):
        used = min(d, capacity)                 # beyond capacity the deduction becomes a carryforward (NOL)
        rest = (extra - used) / spread
        return saved(used) + sum(saved(rest) / (1 + r) ** k for k in range(1, spread + 1))

    vals = [pv(d) for d in grid]
    best_val = max(vals)
    # Many amounts tie once this year's income is used up; recommend the smallest that captures the value.
    best_d = next(d for d, v in zip(grid, vals) if v >= best_val - 250)
    all_val = vals[-1]
    income_after_salary = base - (p.owner_salary if p.entity_type in ("s_corp", "c_corp") else 0)
    creates_loss = extra > income_after_salary
    gain = best_val - all_val
    o.applies = gain > 500 or creates_loss
    o.est_savings = round(max(0.0, gain), 2)
    o.detail = {"accelerated_items": {k: round(v, 2) for k, v in items.items()}, "total_extra_deductions": round(extra, 2),
                "business_income_after_owner_pay_before_acceleration": round(income_after_salary, 2),
                "pv_take_everything_now": round(all_val, 2), "pv_best": round(best_val, 2),
                "this_year_capacity": round(capacity, 2),
                "recommended_extra_deduction_this_year": round(best_d, 2),
                "defer_to_later_years": round(extra - best_d, 2)}
    o.summary = (f"Accelerating everything adds ${extra:,.0f} of deductions against ~${income_after_salary:,.0f} of "
                 f"business income after owner pay" + (" - creating a loss" if creates_loss else "") +
                 f". Deducting about ${best_d:,.0f} extra now and the rest later is worth ~${gain:,.0f} more (PV) "
                 f"than taking it all this year, because deductions beyond income are taxed at low or zero rates.")
    o.assumptions = ["Future income is similar to this year's", f"Discount rate {r:.0%}",
                     f"Deductions not taken now, and any loss carried forward, are recovered evenly over the next "
                     f"{spread} years (the 80% NOL limit and Sec. 461(l) could slow this further)"]
    o.actions = ["Elect out of 100% bonus for selected classes (Sec. 168(k)(7)) and use Sec. 179 asset-by-asset to "
                 "hit the target deduction", "Time the cash-method change or cost segregation catch-up for a "
                 "higher-income year if they push income too low",
                 "Check S corp shareholder basis, at-risk and Sec. 461(l) limits before deducting a loss"]
    o.risks = ["Item estimates elsewhere in this report are each valued alone; this check shows how they interact"]
    o.confidence = "medium"
    return o


def check_wotc(p: CompanyProfile) -> Opportunity:
    o = Opportunity("wotc_watch", "Work Opportunity Tax Credit - expired, watch for renewal", "Credits", False,
                    savings_type="compliance", authority=["IRC 51 (expired for hires after 12/31/2025)", "H.R. 6231 / S. 3265 (pending)"])
    if not p.hiring_new_employees:
        return o
    o.applies = True
    o.summary = ("WOTC is not available for employees who begin work after 12/31/2025 unless Congress renews it "
                 "retroactively (bills pending). Keep screening new hires.")
    o.actions = ["Keep filing Form 8850 within 28 days of each hire so the credit is preserved if renewed retroactively"]
    o.confidence = "medium"
    return o


def check_energy(p: CompanyProfile) -> Opportunity:
    o = Opportunity("energy_deadlines", "Energy incentives - closing windows (179D, 45L, 45Y/48E)", "Credits", False,
                    savings_type="compliance",
                    authority=["OBBBA sec. 70501-70513", "IRS FAQs on P.L. 119-21 energy provisions"])
    if not (p.energy_projects_in_progress or p.building_cost_placed_in_service):
        return o
    o.applies = p.energy_projects_in_progress
    o.summary = ("Sec. 179D is unavailable for property whose construction begins after 6/30/2026; Sec. 45L for homes "
                 "acquired after 6/30/2026; wind/solar under 45Y/48E must have begun construction by 7/4/2026 or be "
                 "placed in service by 12/31/2027. Only projects already underway can still qualify.")
    o.actions = ["Document begin-construction dates (physical work or 5% safe harbor) for projects in progress",
                 "Obtain 179D certifications before the building is placed in service"]
    o.confidence = "medium"
    return o


def check_opportunity_zone(p: CompanyProfile) -> Opportunity:
    o = Opportunity("opportunity_zone", "Defer capital gains through a qualified opportunity fund", "Exit planning", False,
                    savings_type="timing (PV)", authority=["IRC 1400Z-2 as amended by OBBBA sec. 70421"])
    g = p.capital_gain_to_reinvest
    if g <= 0:
        return o
    import datetime
    r = p.discount_rate
    inv = datetime.date.fromisoformat(p.qof_investment_date) if p.qof_investment_date else None
    real = datetime.date.fromisoformat(p.gain_realization_date) if p.gain_realization_date else None
    if real and inv and (inv - real).days > 180:
        o.summary = "The QOF investment must be made within 180 days of realizing the gain."
        return o
    if inv and inv < datetime.date(2027, 1, 1):
        o.summary = ("Under the pre-2027 rules, deferred gain is recognized on 12/31/2026 with no basis step-up, "
                     "so an investment before 2027 gives essentially no deferral - only the 10-year exclusion of "
                     "post-investment appreciation.")
        o.applies = True
        o.risks = ["Wait for the 2027 regime only if the 180-day window allows an investment on/after 1/1/2027"]
        return o
    if not inv:
        o.assumptions.append("Assumes the investment is made on/after 1/1/2027 within 180 days of the gain - "
                             "provide gain_realization_date and qof_investment_date to check")
    step = bparam("oz_rural_step_up" if p.oz_rural_fund else "oz_basis_step_up", p.year)
    t = 0.238
    pv_defer = g * t * (1 - 1 / (1 + r) ** 5)
    pv_step = g * step * t / (1 + r) ** 5
    o.applies = True
    o.est_savings = round(pv_defer + pv_step, 2)
    o.detail = {"deferral_pv": round(pv_defer, 2), "basis_step_up_pv": round(pv_step, 2),
                "post_10_year_appreciation": "excluded (basis steps up to FMV after 10 years)"}
    o.summary = (f"Investing ${g:,.0f} of gain in a QOF (investments after 12/31/2026) defers tax 5 years and "
                 f"steps basis up {step:.0%}; appreciation on the QOF investment is tax-free after 10 years.")
    o.assumptions = ["23.8% capital gain + NIIT rate", f"Discount rate {r:.0%}", "Value excludes the 10-year appreciation benefit"]
    o.actions = ["Invest within 180 days of the gain", "Gains deferred under the old regime must be recognized by 12/31/2026",
                 "Gains realized late in 2026 may be better invested on/after 1/1/2027 for the full 5-year deferral"]
    o.risks = ["Illiquid 10-year commitment; new zone map takes effect 1/1/2027; new reporting penalties"]
    return o


CHECKS: List[Callable[[CompanyProfile], Opportunity]] = [
    check_entity_choice, check_reasonable_comp, check_qbi, check_depreciation, check_cost_segregation, check_qpp,
    check_research_expensing, check_research_credit, check_interest_limit, check_cash_method, check_ptet,
    check_retirement_plan, check_childcare, check_paid_leave, check_qsbs, check_opportunity_zone, check_charity_corp,
    check_wotc, check_energy, check_deduction_capacity, check_compliance,
]


def scan(profile: CompanyProfile | dict, only_applicable: bool = False) -> List[Opportunity]:
    p = profile if isinstance(profile, CompanyProfile) else CompanyProfile.from_dict(profile)
    res = [c(p) for c in CHECKS]
    if only_applicable:
        res = [o for o in res if o.applies]
    return sorted(res, key=lambda o: (not o.applies, -o.est_savings))


def to_dict(o: Opportunity) -> dict:
    return asdict(o)
