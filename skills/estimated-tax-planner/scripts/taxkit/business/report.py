"""Render scan results as Markdown, JSON or an .xlsx summary."""
from __future__ import annotations

import json
from typing import List

from .opportunities import CompanyProfile, Opportunity, to_dict

DISCLAIMER = ("Estimates for planning conversations only - not tax advice. Figures are first-year federal effects "
              "under stated assumptions (timing items shown as present value). Confirm facts, state conformity and "
              "elections with a qualified tax professional before acting.")


def markdown(profile: CompanyProfile, opps: List[Opportunity]) -> str:
    app = [o for o in opps if o.applies]
    cap = next((o for o in opps if o.id == "deduction_capacity"), None)
    out = [f"# Tax opportunity scan - {profile.name} ({profile.year})", "",
           f"**Entity:** {profile.entity_type.replace('_', ' ')} · **Avg. gross receipts:** "
           f"${profile.avg_gross_receipts_3yr:,.0f} · **Profit before owner pay:** ${profile.net_income_before_owner_pay:,.0f}",
           "", f"**{len(app)} opportunities apply.** Each value below is estimated on its own; they are **not additive** "
           "(accelerated deductions compete for the same income)."
           + (f" See *{cap.title}* for the combined effect." if cap and cap.applies else ""), "",
           "| # | Opportunity | Type | Est. value | Confidence |", "|---|---|---|---:|---|"]
    for i, o in enumerate(app, 1):
        out.append(f"| {i} | {o.title} | {o.savings_type} | ${o.est_savings:,.0f} | {o.confidence} |")
    for o in app:
        out += ["", f"## {o.title}", "", o.summary]
        for head, items in (("Assumptions", o.assumptions), ("Actions", o.actions), ("Risks", o.risks),
                            ("Authority", o.authority)):
            if items:
                out += ["", f"**{head}**"] + [f"- {x}" for x in items]
    na = [o for o in opps if not o.applies]
    if na:
        out += ["", "## Checked, not applicable", ""] + [f"- {o.title}" + (f" - {o.summary}" if o.summary else "")
                                                         for o in na]
    out += ["", f"_{DISCLAIMER}_", ""]
    return "\n".join(out)


def as_json(profile: CompanyProfile, opps: List[Opportunity]) -> str:
    return json.dumps({"profile": profile.name, "year": profile.year,
                       "opportunities": [to_dict(o) for o in opps], "disclaimer": DISCLAIMER}, indent=1, default=str)


def xlsx(profile: CompanyProfile, opps: List[Opportunity], path: str) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Opportunities"
    ws.append([f"Tax opportunity scan - {profile.name} ({profile.year})"])
    ws["A1"].font = Font(name="Arial", size=14, bold=True)
    ws.append([DISCLAIMER])
    ws["A2"].font = Font(name="Arial", size=9, italic=True)
    ws.append([])
    head = ["Applies", "Opportunity", "Category", "Type", "Est. value ($)", "Confidence", "Summary", "Actions", "Authority"]
    ws.append(head)
    for c in ws[4]:
        c.font = Font(name="Arial", bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3864")
    for o in opps:
        ws.append(["Yes" if o.applies else "No", o.title, o.category, o.savings_type, round(o.est_savings, 2),
                   o.confidence, o.summary, "\n".join(o.actions), "\n".join(o.authority)])
    last = ws.max_row
    ws.append([])
    ws.append(["", "Values are estimated one at a time and are not additive (see 'Right-size this year's accelerated deductions')."])
    for row in ws.iter_rows(min_row=5):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if c.column == 5:
                c.number_format = '$#,##0;($#,##0);"-"'
    for col, w in zip("ABCDEFGHI", (8, 44, 16, 14, 14, 11, 70, 60, 50)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A5"
    wb.save(path)
    return path
