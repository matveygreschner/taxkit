"""Vendor the engine into each skill, generate the skills' reference files, validate the
skills, and package them as downloadable archives in dist/.

    python scripts/build_skills.py            # build + package
    python scripts/build_skills.py --check    # fail if committed skill files are stale (CI)

Each skill ships its own copy of ``src/taxkit`` so it runs anywhere with Python 3.9+
and no install step (Claude Code, Claude.ai, the API code-execution tool).
"""
from __future__ import annotations

import argparse
import filecmp
import inspect
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from taxkit import api, params as P  # noqa: E402
import importlib  # noqa: E402

for _mod in api.ADDONS:  # register every add-on's commands (never names a package that isn't there)
    importlib.import_module(_mod)
from taxkit.business.bparams import BPARAMS  # noqa: E402
from taxkit.business.opportunities import Asset, CompanyProfile  # noqa: E402

SKILLS = ROOT / "skills"
DIST = ROOT / "dist"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")

GROUPS = [
    ("Rates & returns", ["income_tax", "ordinary_tax", "bracket_breakdown", "per_band_min_tax", "form_1040", "params"]),
    ("Individual", ["standard_deduction", "senior_deduction", "tips_deduction", "overtime_deduction",
                    "car_loan_interest_deduction", "child_tax_credit", "kiddie_tax", "taxable_social_security",
                    "qbi_deduction"]),
    ("Itemized deductions", ["itemized_deductions", "salt_cap", "charitable_deduction", "mortgage_interest_deduction",
                             "medical_deduction", "gambling_loss_deduction"]),
    ("Payroll", ["fica", "self_employment_tax", "niit"]),
    ("Property", ["amount_realized", "adjusted_basis", "sale", "home_sale_exclusion", "net_capital_gains",
                  "foreclosure", "gift_basis", "converted_property_basis"]),
    ("Entities", ["owner_reporting", "basis_rollforward", "c_corp_tax", "double_tax_burden"]),
    ("Depreciation & amortization", ["macrs_table", "personal_property_schedule", "real_property_depreciation",
                                     "sec179_allowed", "needs_mid_quarter", "startup_costs", "sec197_amortization",
                                     "cost_depletion", "percentage_depletion"]),
    ("Income items", ["imputed_interest", "annuity_exclusion", "group_term_life_income", "feie", "ltc_taxable",
                      "scholarship_taxable", "oid_accrual", "tax_benefit_refund_income"]),
    ("Losses", ["casualty_loss", "excess_business_loss", "apply_nol", "compute_nol", "vacation_home"]),
    ("Retirement", ["traditional_ira_deduction", "roth_contribution_limit", "sep_deduction"]),
    ("Live data", ["sec_tax_profile", "underpayment_rate"]),
    ("Business optimizer", ["business_scan", "compare_entities", "reasonable_comp_sweep", "qbi_deduction_full"]),
    ("Estimated tax", ["safe_harbor", "underpayment_penalty", "year_end_projection", "estimate_vouchers",
                       "installment_due_dates"]),
    ("Output", ["workbook"]),
]


def _fmt(v):
    if isinstance(v, str):
        return f'"{v}"' if v != "REQUIRED" else "**required**"
    return repr(v)


CORE = [g for g, _ in GROUPS if g not in ("Business optimizer", "Estimated tax")]
SKILL_GROUPS = {   # each skill's documented commands (every bundle carries the whole package)
    "us-tax-calculator": (CORE, "tax"),
    "business-tax-optimizer": (CORE + ["Business optimizer"], "optimize"),
    "estimated-tax-planner": (["Estimated tax", "Rates & returns", "Payroll", "Retirement", "Live data"], "estimate"),
}
CODE_SKILLS = tuple(SKILL_GROUPS)


def commands_md(groups) -> str:
    out = ["# Command reference", "",
           "Run `python scripts/<entry>.py <command> '<json>'`. Arguments not listed as required are optional.", ""]
    listed = set()
    for title, names in groups:
        out += [f"## {title}", ""]
        for n in names:
            d = api.describe(n)
            listed.add(n)
            first = d["doc"].split("\n\n")[0].replace("\n", " ") if d["doc"] else ""
            args = ", ".join(f"`{k}`={_fmt(v)}" for k, v in d["args"].items()) or "(none)"
            out += [f"### `{n}`", "", first, "", f"Args: {args}", ""]
    missing = sorted(set(api.COMMANDS) - {n for _, names in GROUPS for n in names})
    assert not missing, f"commands missing from GROUPS: {missing}"
    return "\n".join(out)


def money(v):
    if isinstance(v, float) and v <= 1:
        return f"{v:.2%}".rstrip("0").rstrip(".") + ("" if f"{v:.2%}".endswith("%") else "")
    return f"${v:,.0f}" if isinstance(v, (int, float)) and v >= 1 else str(v)


def rates_md() -> str:
    out = ["# Rates and limits, 2025 and 2026", "",
           "Generated from `taxkit/params.py`. Sources: Rev. Proc. 2024-40 (2025, as amended by OBBBA), "
           "Rev. Proc. 2025-32 (2026).", "", "## Ordinary brackets (lower bound of each rate)", ""]
    for y in P.YEARS:
        out += [f"### {y}", "", "| Rate | " + " | ".join(P.STATUSES[:4]) + " |", "|---|" + "---:|" * 4]
        for i, rate in enumerate(P.ORDINARY_RATES):
            out.append(f"| {rate:.0%} | " + " | ".join(f"${P.ordinary_brackets(y, s)[i][0]:,.0f}"
                                                         for s in P.STATUSES[:4]) + " |")
        out += ["", "Capital gains: 0% up to / 15% up to: " + "; ".join(
            f"{s} ${P.capital_gain_brackets(y, s)[1][0]:,.0f} / ${P.capital_gain_brackets(y, s)[2][0]:,.0f}"
            for s in P.STATUSES[:4]), ""]
    out += ["## Parameters", "", "| Key | Description | 2025 | 2026 | Source |", "|---|---|---|---|---|"]
    for k, e in P.PARAMS.items():
        def cell(y):
            v = e[y]
            if isinstance(v, dict):
                return "; ".join(f"{s} {money(v[s])}" for s in ("S", "MFJ", "MFS", "HOH"))
            return money(v)
        out.append(f"| `{k}` | {e['desc']} | {cell(2025)} | {cell(2026)} | {e['source']} |")
    return "\n".join(out) + "\n"


def bparams_md() -> str:
    out = ["# Business parameters, 2025 and 2026", "", "Generated from `taxkit/business/bparams.py`.", "",
           "| Key | Description | 2025 | 2026 | Source |", "|---|---|---|---|---|"]
    for k, e in BPARAMS.items():
        def cell(y):
            v = e[y]
            if isinstance(v, dict):
                return "; ".join(f"{s} {money(v[s])}" for s in ("S", "MFJ"))
            return money(v)
        out.append(f"| `{k}` | {e['desc']} | {cell(2025)} | {cell(2026)} | {e['source']} |")
    return "\n".join(out) + "\n"


FIELD_HELP = {
    "entity_type": "sole_prop | partnership | s_corp | c_corp",
    "sstb": "specified service business (health, law, accounting, consulting, financial services...)",
    "avg_gross_receipts_3yr": "3-year average gross receipts (Sec. 448(c) test)",
    "net_income_before_owner_pay": "profit after ordinary expenses (incl. domestic R&D, which is expensed by default) "
                                   "but BEFORE owner salary/guaranteed payments and BEFORE depreciation on the assets "
                                   "and building listed in this profile",
    "owner_salary": "W-2 salary to the owner (S/C corp) or guaranteed payments (partnership)",
    "owner_other_salt": "owner's property tax + other state/local taxes (for the SALT cap / PTET math)",
    "non_owner_wages": "W-2 wages to employees other than the owner",
    "ubia": "unadjusted basis of qualified property (Sec. 199A)",
    "state_income_tax_rate": "flat state income tax rate on business income (illustrative)",
    "unamortized_domestic_re_2022_2024": "remaining unamortized domestic R&E capitalized in 2022-2024",
    "qualified_research_expenses": "current-year QREs for the Sec. 41 credit",
    "prior_3yr_qres": "QREs for each of the 3 prior years, oldest first",
    "ebitda": "earnings before interest, taxes, depreciation and amortization (for Sec. 163(j))",
    "nhce_count": "non-highly compensated employees (plan startup credit)",
    "qsbs_issued_after_jul4_2025": "true if the stock was issued after July 4, 2025 (new tiered rules)",
    "qsbs_gross_assets_at_issuance": "corporation's aggregate gross assets when the stock was issued",
    "discount_rate": "rate used to present-value timing benefits",
    "building_used_in_production": "building houses manufacturing/production (Sec. 168(n) candidate)",
    "building_original_use": "false if the building was bought used",
    "as_of": "date of the scan (YYYY-MM-DD); drives deadline checks, defaults to today",
    "re_catchup_elected": "none | one_year | two_year - the Sec. 174A catch-up choice made on the 2025 return",
    "method": "law (default) or simplified",
}


def profile_md() -> str:
    out = ["# Company profile fields", "", "Pass these to `business_scan` as `{\"profile\": {...}}`. All are optional; "
           "unknown amounts default to zero, so checks that need them simply don't apply.", "",
           "| Field | Default | Meaning |", "|---|---|---|"]
    for name, prm in inspect.signature(CompanyProfile).parameters.items():
        d = prm.default
        d = "[]" if name in ("assets", "prior_3yr_qres") else repr(d)
        out.append(f"| `{name}` | {d} | {FIELD_HELP.get(name, '')} |")
    out += ["", "`assets` items:", "", "| Field | Default | Meaning |", "|---|---|---|"]
    for name, prm in inspect.signature(Asset).parameters.items():
        d = "**required**" if prm.default is inspect.Parameter.empty else repr(prm.default)
        out.append(f"| `{name}` | {d} | |")
    return "\n".join(out) + "\n"


def write(path: Path, text: str, check: bool, stale: list):
    if check:
        if not path.exists() or path.read_text() != text:
            stale.append(str(path.relative_to(ROOT)))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def vendor(skill: str, check: bool, stale: list):
    dest = SKILLS / skill / "scripts" / "taxkit"
    src = ROOT / "src" / "taxkit"
    if check:
        cmp = filecmp.dircmp(src, dest, ignore=["__pycache__"]) if dest.exists() else None

        def diff(c):
            return bool(c.left_only or c.right_only or c.diff_files) or any(diff(s) for s in c.subdirs.values())
        if cmp is None or diff(cmp):
            stale.append(str(dest.relative_to(ROOT)))
        return
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=IGNORE)


def validate(skill_dir: Path) -> list:
    errs = []
    text = (skill_dir / "SKILL.md").read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return [f"{skill_dir.name}: SKILL.md has no YAML frontmatter"]
    fm = dict(re.findall(r"^(\w[\w-]*):\s*(.+)$", m.group(1), re.M))
    if fm.get("name") != skill_dir.name:
        errs.append(f"{skill_dir.name}: frontmatter name {fm.get('name')!r} must match folder")
    if not re.fullmatch(r"[a-z0-9-]{1,64}", fm.get("name", "")):
        errs.append(f"{skill_dir.name}: name must be lowercase letters, digits, hyphens")
    desc = fm.get("description", "")
    if not desc or len(desc) > 1024 or "<" in desc or ">" in desc:
        errs.append(f"{skill_dir.name}: description missing, >1024 chars, or contains angle brackets")
    if len(text.splitlines()) > 500:
        errs.append(f"{skill_dir.name}: SKILL.md over 500 lines")
    for ref in re.findall(r"`((?:references|scripts|assets)/[^`\s]+)`", text):
        if not (skill_dir / ref).exists():
            errs.append(f"{skill_dir.name}: SKILL.md mentions missing file {ref}")
    return errs


def package(skill_dir: Path) -> list:
    DIST.mkdir(exist_ok=True)
    made = []
    for ext in (".zip", ".skill"):
        out = DIST / f"{skill_dir.name}{ext}"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(skill_dir.rglob("*")):
                rel = f.relative_to(skill_dir.parent)
                if f.is_dir() or "__pycache__" in rel.parts or f.suffix == ".pyc" or f.name == ".DS_Store" \
                        or (len(rel.parts) > 1 and rel.parts[1] == "evals"):
                    continue
                zi = zipfile.ZipInfo(str(rel).replace("\\", "/"), date_time=(2026, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o644 << 16
                z.writestr(zi, f.read_bytes())
        made.append(out)
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    stale: list = []
    for skill in CODE_SKILLS:
        vendor(skill, a.check, stale)
    for skill, (names, entry) in SKILL_GROUPS.items():
        groups = [g for g in GROUPS if g[0] in names]
        groups.sort(key=lambda g: names.index(g[0]))
        write(SKILLS / skill / "references/commands.md", commands_md(groups).replace("<entry>", entry), a.check, stale)
    write(SKILLS / "us-tax-calculator/references/rates-2025-2026.md", rates_md(), a.check, stale)
    write(SKILLS / "business-tax-optimizer/references/profile-fields.md", profile_md(), a.check, stale)
    write(SKILLS / "business-tax-optimizer/references/business-parameters.md", bparams_md(), a.check, stale)
    errs = [e for d in sorted(SKILLS.iterdir()) if d.is_dir() for e in validate(d)]
    if errs or stale:
        for e in errs:
            print("INVALID", e)
        for s in stale:
            print("STALE  ", s, "- run python scripts/build_skills.py")
        sys.exit(1)
    if a.check:
        print("skills are valid and up to date")
        return
    for d in sorted(SKILLS.iterdir()):
        if d.is_dir():
            for f in package(d):
                print("packaged", f.relative_to(ROOT), f"{f.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
