"""Business-tax parameters for 2025 and 2026 (post-OBBBA, P.L. 119-21).

Each entry carries its source so the optimizer's report can cite it.
"""
from __future__ import annotations

from typing import Dict

from ..params import DEFAULT_YEAR


def _st(s, mfj, mfs=None, hoh=None):
    return {"S": s, "MFJ": mfj, "MFS": s if mfs is None else mfs, "HOH": s if hoh is None else hoh, "QSS": mfj}


BPARAMS: Dict[str, dict] = {
    "gross_receipts_test": {"desc": "Sec. 448(c) small business gross receipts test (3-yr average)",
                            "source": "Rev. Proc. 2024-40 sec. 3.32; Rev. Proc. 2025-32", 2025: 31_000_000,
                            2026: 32_000_000},
    "interest_limit_pct": {"desc": "Sec. 163(j) limit as % of adjusted taxable income", "source": "IRC 163(j)(1)",
                           2025: 0.30, 2026: 0.30},
    "rd_asc_rate": {"desc": "Research credit - alternative simplified credit rate", "source": "IRC 41(c)(4)",
                    2025: 0.14, 2026: 0.14},
    "rd_asc_startup_rate": {"desc": "ASC rate if no QREs in any of the 3 prior years", "source": "IRC 41(c)(4)(B)",
                            2025: 0.06, 2026: 0.06},
    "rd_payroll_offset_max": {"desc": "Research credit payroll tax offset - qualified small business",
                              "source": "IRC 41(h); IRA 2022 sec. 13902", 2025: 500_000, 2026: 500_000},
    "rd_qsb_receipts": {"desc": "Qualified small business: gross receipts under (current year)", "source": "IRC 41(h)(3)",
                        2025: 5_000_000, 2026: 5_000_000},
    "qsbs_cap": {"desc": "Sec. 1202 per-issuer cap (stock issued after 7/4/2025)", "source": "IRC 1202(b); OBBBA sec. 70431",
                 2025: 15_000_000, 2026: 15_000_000},
    "qsbs_cap_old": {"desc": "Sec. 1202 per-issuer cap (stock issued on/before 7/4/2025)", "source": "IRC 1202(b)",
                     2025: 10_000_000, 2026: 10_000_000},
    "qsbs_assets": {"desc": "Sec. 1202 aggregate gross assets limit at issuance (post-7/4/2025)",
                    "source": "IRC 1202(d); OBBBA sec. 70431", 2025: 75_000_000, 2026: 75_000_000},
    "qsbs_assets_old": {"desc": "Sec. 1202 aggregate gross assets limit (pre-7/5/2025 issuance)", "source": "IRC 1202(d)",
                        2025: 50_000_000, 2026: 50_000_000},
    "camt_threshold": {"desc": "Corporate AMT applies above 3-yr average AFSI of", "source": "IRC 55, 59(k)",
                       2025: 1_000_000_000, 2026: 1_000_000_000},
    "childcare_credit_rate": {"desc": "Sec. 45F employer childcare credit rate (non-small business)",
                              "source": "IRC 45F; OBBBA sec. 70401", 2025: 0.25, 2026: 0.40},
    "childcare_credit_rate_small": {"desc": "Sec. 45F rate for eligible small businesses (5-yr Sec. 448(c) test)",
                                    "source": "OBBBA sec. 70401; IRS Employer-provided child care credit page",
                                    2025: 0.25, 2026: 0.50},
    "childcare_credit_max": {"desc": "Sec. 45F maximum credit", "source": "OBBBA sec. 70401", 2025: 150_000,
                             2026: 500_000},
    "childcare_credit_max_small": {"desc": "Sec. 45F maximum credit - eligible small business",
                                   "source": "OBBBA sec. 70401", 2025: 150_000, 2026: 600_000},
    "startup_plan_credit_max": {"desc": "Sec. 45E startup plan credit cap per year (first 3 years)",
                                "source": "IRC 45E; SECURE 2.0 sec. 102", 2025: 5_000, 2026: 5_000},
    "auto_enroll_credit": {"desc": "Sec. 45T auto-enrollment credit per year (3 years)", "source": "IRC 45T",
                           2025: 500, 2026: 500},
    "employer_contrib_credit_per_ee": {"desc": "SECURE 2.0 employer contribution credit per employee (max)",
                                       "source": "IRC 45E(f)", 2025: 1_000, 2026: 1_000},
    "de_minimis_no_afs": {"desc": "De minimis safe harbor per item - no AFS", "source": "Reg. 1.263(a)-1(f)",
                          2025: 2_500, 2026: 2_500},
    "de_minimis_afs": {"desc": "De minimis safe harbor per item - with AFS", "source": "Reg. 1.263(a)-1(f)",
                       2025: 5_000, 2026: 5_000},
    "bonus_pre_jan20_2025": {"desc": "Bonus % for property acquired before 1/20/2025, placed in service 2025",
                             "source": "IRC 168(k)(8)", 2025: 0.40, 2026: 0.20},
    "sec179_suv_cap": {"desc": "Sec. 179 cap for heavy SUVs (6,001-14,000 lbs)", "source": "IRC 179(b)(5); Rev. Proc. 2025-32",
                       2025: 31_300, 2026: 32_000},
    "plan_credit_rate_small": {"desc": "Sec. 45E startup credit rate, <= 50 employees (51-100: 50%)",
                               "source": "IRC 45E(e)(4)", 2025: 1.00, 2026: 1.00},
    "nhce_credit_per": {"desc": "Sec. 45E startup credit: $ per eligible NHCE", "source": "IRC 45E(b)(1)",
                        2025: 250, 2026: 250},
    "contrib_credit_wage_cap": {"desc": "Employer contribution credit: employees with FICA wages over this excluded",
                                "source": "IRC 45E(f); Form 8881 instructions; Notice 2025-67", 2025: 105_000,
                                2026: 110_000},
    "small_bldg_receipts": {"desc": "Small taxpayer building safe harbor: average gross receipts limit",
                            "source": "Reg. 1.263(a)-3(h)", 2025: 10_000_000, 2026: 10_000_000},
    "oz_basis_step_up": {"desc": "Opportunity zone basis step-up after 5 years (investments after 12/31/2026)",
                         "source": "IRC 1400Z-2(b)(2)(B) as amended by OBBBA sec. 70421", 2025: 0.10, 2026: 0.10},
    "oz_rural_step_up": {"desc": "Qualified rural opportunity fund step-up after 5 years", "source": "OBBBA sec. 70421",
                         2025: 0.30, 2026: 0.30},
    "info_return_penalty": {"desc": "Information return penalty per return (returns due in 2026)", "source": "IRC 6721; Rev. Proc. 2024-40",
                            2025: 340, 2026: 340},
    "nec_1099_threshold": {"desc": "Form 1099-NEC/MISC reporting threshold", "source": "OBBBA sec. 70433",
                           2025: 600, 2026: 2_000},
}


def bparam(key: str, year: int = DEFAULT_YEAR, status: str | None = None):
    if key not in BPARAMS:                      # shared parameters live in taxkit.params
        from ..params import PARAMS, param
        if key in PARAMS:
            return param(key, year, status or "S") if isinstance(PARAMS[key][year], dict) else param(key, year)
    v = BPARAMS[key][year]
    if isinstance(v, dict):
        return v[status or "S"]
    return v
