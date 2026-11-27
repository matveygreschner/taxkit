"""Business tax optimization: entity choice, cost recovery, R&D, financing, state, benefits, exit planning."""
from __future__ import annotations

from .. import api
from .entity import compare_entities, qbi_deduction_full, reasonable_comp_sweep
from .opportunities import Asset, CompanyProfile, Opportunity, scan
from .report import as_json, markdown, xlsx


def _scan(profile: dict | None = None, only_applicable: bool = False, format: str = "json", xlsx_path: str = ""):
    """Scan a company profile (dict of CompanyProfile fields; ``assets`` is a list of Asset dicts) for federal
    tax opportunities. ``format``: json | markdown. ``xlsx_path`` also writes an Excel summary."""
    p = CompanyProfile.from_dict(profile or {})
    opps = scan(p, only_applicable)
    if xlsx_path:
        xlsx(p, opps, xlsx_path)
    if format == "markdown":
        return {"markdown": markdown(p, opps)}
    return opps


api.register("business_scan", _scan)
api.register("compare_entities", compare_entities)
api.register("reasonable_comp_sweep", reasonable_comp_sweep)
api.register("qbi_deduction_full", qbi_deduction_full)

__all__ = ["Asset", "CompanyProfile", "Opportunity", "scan", "compare_entities", "reasonable_comp_sweep",
           "qbi_deduction_full", "markdown", "as_json", "xlsx"]
