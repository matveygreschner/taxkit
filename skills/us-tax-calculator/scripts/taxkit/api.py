"""JSON command interface over the engine - used by the Claude skills and scripts.

    python -m taxkit.api list                          # every command and its arguments
    python -m taxkit.api describe income_tax           # one command's arguments + docstring
    python -m taxkit.api income_tax '{"taxable_income": 400000, "status": "S", "net_ltcg": 400000}'
    echo '{"wages": 150000, "status": "MFJ"}' | python -m taxkit.api form_1040 -

Output is always JSON: {"command": ..., "inputs": ..., "result": ...} or {"error": ...}.
"""
from __future__ import annotations

import dataclasses
import inspect
import json
import sys
from typing import Any, Callable, Dict

from . import depreciation as dep
from . import entities as ent
from . import income as inc
from . import individual as ind
from . import itemized as itm
from . import losses as los
from . import params as P
from . import payroll as pay
from . import property as prop
from . import live, rates
from . import retirement as ret
from .form1040 import Return1040, compute_return


def _form_1040(**kw):
    """Complete Form 1040. Some amounts are entered twice on purpose, as on the real form:
    ``ordinary_dividends`` INCLUDES ``qualified_dividends``; ``net_capital_gain`` is the Schedule D net
    (a loss is limited to -3,000) and ``net_ltcg_for_rates`` is the part eligible for 0/15/20%;
    ``net_investment_income`` (for NIIT) is not derived automatically.

    Pass any Return1040 field (year, status, method, wages, taxable_interest,
    ordinary_dividends, qualified_dividends, net_capital_gain, net_ltcg_for_rates, schedule_c_profit,
    other_income, taxable_social_security, se_health_insurance, se_retirement, ira_deduction,
    student_loan_interest, educator_expenses, alimony_paid, other_adjustments, age65_or_blind_boxes,
    num_seniors, qualified_tips, qualified_overtime, car_loan_interest, other_qbi, qualifying_children,
    other_dependents, other_credits, net_investment_income, withholding, estimated_payments) and
    ``itemized`` = dict of itemized_deductions() arguments (medical_expenses, state_local_taxes,
    mortgage_interest, mortgage_avg_balance, charity_cash_public, ...)."""
    return compute_return(Return1040(**kw))


_form_1040.__signature__ = inspect.signature(Return1040)   # so `describe form_1040` lists every field


def _params(year: int = P.DEFAULT_YEAR, status: str | None = None, key: str | None = None):
    """Look up tax-year parameters. With ``key`` returns one value; otherwise every parameter
    (status-dependent ones for ``status`` if given, else all statuses) with its source."""
    if key:
        return {"key": key, "value": P.param(key, year, status) if P.is_status_param(key) else P.param(key, year),
                "desc": P.PARAMS[key]["desc"], "source": P.PARAMS[key]["source"]}
    out = {}
    for k, e in P.PARAMS.items():
        v = e[year]
        if isinstance(v, dict) and status:
            v = v.get(status, v.get("MFJ"))
        out[k] = {"value": v, "desc": e["desc"], "source": e["source"]}
    out["ordinary_brackets"] = {s: P.ordinary_brackets(year, s) for s in P.STATUSES} if not status else \
        P.ordinary_brackets(year, status)
    out["capital_gain_brackets"] = {s: P.capital_gain_brackets(year, s) for s in P.STATUSES} if not status else \
        P.capital_gain_brackets(year, status)
    return out


def _basis_rollforward(contributions, net_income, distributions, ownership_pct=1.0, beginning_basis=0.0):
    """Partner / S corp outside basis year by year (lists of equal length)."""
    return ent.basis_rollforward(contributions, net_income, distributions, ownership_pct, beginning_basis)


def _workbook(out: str = "TaxKit.xlsx"):
    """Generate the formula-driven Excel / Google Sheets workbook (requires openpyxl)."""
    from .excel.builder import build_workbook
    build_workbook(out)
    return {"written": out}


COMMANDS: Dict[str, Callable[..., Any]] = {
    # rates & returns
    "income_tax": rates.income_tax,
    "ordinary_tax": rates.ordinary_tax,
    "bracket_breakdown": rates.bracket_breakdown,
    "per_band_min_tax": rates.per_band_min_tax,
    "form_1040": _form_1040,
    "params": _params,
    # individual
    "standard_deduction": ind.standard_deduction,
    "senior_deduction": ind.senior_deduction,
    "tips_deduction": ind.tips_deduction,
    "overtime_deduction": ind.overtime_deduction,
    "car_loan_interest_deduction": ind.car_loan_interest_deduction,
    "child_tax_credit": ind.child_tax_credit,
    "kiddie_tax": ind.kiddie_tax,
    "taxable_social_security": ind.taxable_social_security,
    "qbi_deduction": ind.qbi_deduction,
    # itemized
    "itemized_deductions": itm.itemized_deductions,
    "salt_cap": itm.salt_cap,
    "charitable_deduction": itm.charitable_deduction,
    "mortgage_interest_deduction": itm.mortgage_interest_deduction,
    "medical_deduction": itm.medical_deduction,
    "gambling_loss_deduction": itm.gambling_loss_deduction,
    # payroll
    "fica": pay.fica,
    "self_employment_tax": pay.self_employment_tax,
    "niit": pay.niit,
    # property
    "amount_realized": prop.amount_realized,
    "adjusted_basis": prop.adjusted_basis,
    "sale": prop.sale,
    "home_sale_exclusion": prop.home_sale_exclusion,
    "net_capital_gains": prop.net_capital_gains,
    "foreclosure": prop.foreclosure,
    "gift_basis": prop.gift_basis,
    "converted_property_basis": prop.converted_property_basis,
    # entities
    "owner_reporting": ent.owner_reporting,
    "basis_rollforward": _basis_rollforward,
    "c_corp_tax": ent.c_corp_tax,
    "double_tax_burden": ent.double_tax_burden,
    # depreciation
    "macrs_table": dep.macrs_table,
    "personal_property_schedule": dep.personal_property_schedule,
    "real_property_depreciation": dep.real_property_depreciation,
    "sec179_allowed": dep.sec179_allowed,
    "needs_mid_quarter": dep.needs_mid_quarter,
    "startup_costs": dep.startup_costs,
    "sec197_amortization": dep.sec197_amortization,
    "cost_depletion": dep.cost_depletion,
    "percentage_depletion": dep.percentage_depletion,
    # income items
    "imputed_interest": inc.imputed_interest,
    "annuity_exclusion": inc.annuity_exclusion,
    "group_term_life_income": inc.group_term_life_income,
    "feie": inc.feie,
    "ltc_taxable": inc.ltc_taxable,
    "scholarship_taxable": inc.scholarship_taxable,
    "oid_accrual": inc.oid_accrual,
    "tax_benefit_refund_income": inc.tax_benefit_refund_income,
    # losses
    "casualty_loss": los.casualty_loss,
    "excess_business_loss": los.excess_business_loss,
    "apply_nol": los.apply_nol,
    "compute_nol": los.compute_nol,
    "vacation_home": los.vacation_home,
    # retirement
    "traditional_ira_deduction": ret.traditional_ira_deduction,
    "roth_contribution_limit": ret.roth_contribution_limit,
    "sep_deduction": ret.sep_deduction,
    # live data (feed rows fetched by a connected SEC / IRS data tool)
    "sec_tax_profile": live.sec_tax_profile,
    "underpayment_rate": live.underpayment_rate,
    # output
    "workbook": _workbook,
}


def register(name: str, fn: Callable[..., Any]) -> None:
    """Let add-on modules (e.g. the business optimizer) expose commands."""
    COMMANDS[name] = fn


def to_jsonable(x: Any) -> Any:
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        d = {f.name: to_jsonable(getattr(x, f.name)) for f in dataclasses.fields(x)}
        for name in dir(type(x)):           # include @property values (e.g. totals)
            if isinstance(getattr(type(x), name, None), property):
                d[name] = to_jsonable(getattr(x, name))
        return d
    if isinstance(x, dict):
        return {str(k): to_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [to_jsonable(v) for v in x]
    if isinstance(x, float):
        return round(x, 6)
    return x


def describe(name: str) -> dict:
    fn = COMMANDS[name]
    sig = inspect.signature(fn)
    args = {}
    for p in sig.parameters.values():
        if p.kind in (p.VAR_KEYWORD, p.VAR_POSITIONAL):
            continue
        args[p.name] = "REQUIRED" if p.default is inspect.Parameter.empty else p.default
    return {"command": name, "args": args, "doc": inspect.getdoc(fn) or ""}


def _finite(x, path="args"):
    import math
    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError(f"{path} must be a finite number")
    if isinstance(x, dict):
        for k, v in x.items():
            _finite(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            _finite(v, f"{path}[{i}]")


def run(name: str, args: dict | None = None) -> dict:
    if name not in COMMANDS:
        return {"error": f"unknown command {name!r}", "available": sorted(COMMANDS)}
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return {"error": "arguments must be a JSON object, e.g. '{\"taxable_income\": 50000}'"}
    try:
        _finite(args)
        result = COMMANDS[name](**args)
        out = {"command": name, "inputs": args, "result": to_jsonable(result)}
        _finite(out["result"], "result")
    except TypeError as e:
        return {"error": str(e), "usage": describe(name)}
    except (ValueError, KeyError, IndexError, ZeroDivisionError, OverflowError) as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return out


# Add-on packages that register their own commands. Append a package here only in the commit that
# creates it, so every listed module exists and an import failure is a real bug that should surface.
ADDONS = ("taxkit.business", "taxkit.estimates")


def _load_optional_modules():
    import importlib
    for mod in ADDONS:
        importlib.import_module(mod)
    # When run as ``python -m taxkit.api`` this module is __main__, a different object from
    # ``taxkit.api`` (where add-ons register), so merge the registries.
    COMMANDS.update(importlib.import_module("taxkit.api").COMMANDS)


def main(argv=None) -> int:
    _load_optional_modules()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "list":
        print(json.dumps({n: describe(n)["args"] for n in sorted(COMMANDS)}, indent=1, default=str))
        return 0
    if cmd == "describe":
        if len(argv) < 2 or argv[1] not in COMMANDS:
            print(json.dumps({"error": "usage: describe <command>", "available": sorted(COMMANDS)}))
            return 2
        print(json.dumps(describe(argv[1]), indent=1, default=str))
        return 0
    raw = argv[1] if len(argv) > 1 else "{}"
    if raw == "-":
        raw = sys.stdin.read()
    def _no_constants(c):
        raise ValueError(f"non-finite number {c} is not allowed")
    try:
        args = json.loads(raw, parse_constant=_no_constants) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError) as e:
        print(json.dumps({"error": f"arguments must be a JSON object: {e}"}))
        return 2
    if not isinstance(args, dict):
        print(json.dumps({"error": "arguments must be a JSON object, not " + type(args).__name__}))
        return 2
    out = run(cmd, args)
    try:
        print(json.dumps(out, indent=1, default=str, allow_nan=False))
    except ValueError as e:
        print(json.dumps({"error": f"result could not be serialized: {e}"}))
        return 1
    return 1 if "error" in out else 0


if __name__ == "__main__":
    sys.exit(main())
