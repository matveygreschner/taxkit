"""Tax-year parameters for U.S. federal individual and business income tax.

Every number here is used by both the Python engine and the generated Excel
workbook (the workbook's ``Rates`` and ``Brackets`` sheets are written from
this module), so there is exactly one source of truth.

Sources
-------
* 2025: Rev. Proc. 2024-40, as amended by P.L. 119-21 (the "One Big Beautiful
  Bill Act", OBBBA, signed July 4, 2025).
* 2026: Rev. Proc. 2025-32 (inflation adjustments reflecting OBBBA).
* SSA wage base announcements (2025: $176,100; 2026: $184,500).
* IRS Notice 2024-80 / Notice 2025-67 (retirement plan limits).

Filing status codes: ``S`` (single), ``MFJ`` (married filing jointly),
``MFS`` (married filing separately), ``HOH`` (head of household),
``QSS`` (qualifying surviving spouse - uses MFJ brackets/standard deduction).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

STATUSES: Tuple[str, ...] = ("S", "MFJ", "MFS", "HOH", "QSS")
STATUS_NAMES = {
    "S": "Single",
    "MFJ": "Married filing jointly",
    "MFS": "Married filing separately",
    "HOH": "Head of household",
    "QSS": "Qualifying surviving spouse",
}
YEARS: Tuple[int, ...] = (2025, 2026)
DEFAULT_YEAR = 2026

ORDINARY_RATES: Tuple[float, ...] = (0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37)

# Lower bound of each ordinary bracket (taxable income), per year and status.
_ORD_LOWER: Dict[int, Dict[str, Tuple[int, ...]]] = {
    2025: {
        "S": (0, 11_925, 48_475, 103_350, 197_300, 250_525, 626_350),
        "MFJ": (0, 23_850, 96_950, 206_700, 394_600, 501_050, 751_600),
        "MFS": (0, 11_925, 48_475, 103_350, 197_300, 250_525, 375_800),
        "HOH": (0, 17_000, 64_850, 103_350, 197_300, 250_500, 626_350),
    },
    2026: {
        "S": (0, 12_400, 50_400, 105_700, 201_775, 256_225, 640_600),
        "MFJ": (0, 24_800, 100_800, 211_400, 403_550, 512_450, 768_700),
        "MFS": (0, 12_400, 50_400, 105_700, 201_775, 256_225, 384_350),
        "HOH": (0, 17_700, 67_450, 105_700, 201_750, 256_200, 640_600),
    },
}

# Top of the 0% and 15% long-term capital gain / qualified dividend bands.
_CG_TOPS: Dict[int, Dict[str, Tuple[int, int]]] = {
    2025: {"S": (48_350, 533_400), "MFJ": (96_700, 600_050),
           "MFS": (48_350, 300_000), "HOH": (64_750, 566_700)},
    2026: {"S": (49_450, 545_500), "MFJ": (98_900, 613_700),
           "MFS": (49_450, 306_850), "HOH": (66_200, 579_600)},
}


def _status_key(status: str) -> str:
    if status not in STATUSES:
        raise ValueError(f"Unknown filing status {status!r}; use one of {STATUSES}")
    return "MFJ" if status == "QSS" else status


def ordinary_brackets(year: int, status: str) -> List[Tuple[float, float]]:
    """Return ``[(lower_bound, rate), ...]`` for the ordinary rate schedule."""
    lows = _ORD_LOWER[year][_status_key(status)]
    return list(zip(lows, ORDINARY_RATES))


def capital_gain_brackets(year: int, status: str) -> List[Tuple[float, float]]:
    """Return ``[(lower_bound, rate), ...]`` for the 0/15/20% schedule."""
    top0, top15 = _CG_TOPS[year][_status_key(status)]
    return [(0, 0.0), (top0, 0.15), (top15, 0.20)]


# ---------------------------------------------------------------------------
# Scalar parameters.  Each entry: key -> {"desc", "source", 2025: v, 2026: v}
# Status-dependent entries use a dict {status: value} for each year.
# ---------------------------------------------------------------------------
def _by_status(s, mfj, mfs, hoh, qss=None):
    return {"S": s, "MFJ": mfj, "MFS": mfs, "HOH": hoh, "QSS": mfj if qss is None else qss}


PARAMS: Dict[str, dict] = {
    # --- Standard deduction ---------------------------------------
    "std_deduction": {
        "desc": "Basic standard deduction",
        "source": "OBBBA sec. 70102; Rev. Proc. 2025-32 sec. 4.15",
        2025: _by_status(15_750, 31_500, 15_750, 23_625),
        2026: _by_status(16_100, 32_200, 16_100, 24_150),
    },
    "std_additional": {
        "desc": "Additional std. deduction per age-65+/blind box",
        "source": "IRC 63(f); Rev. Proc. 2025-32",
        2025: _by_status(2_000, 1_600, 1_600, 2_000, 1_600),
        2026: _by_status(2_050, 1_650, 1_650, 2_050, 1_650),
    },
    "dep_std_min": {"desc": "Dependent std. deduction minimum", "source": "IRC 63(c)(5)",
                    2025: 1_350, 2026: 1_350},
    "dep_std_earned_addon": {"desc": "Dependent std. deduction: earned income + this",
                             "source": "IRC 63(c)(5)", 2025: 450, 2026: 450},
    "kiddie_threshold": {"desc": "Kiddie tax: unearned income threshold (2x dep. min.)",
                         "source": "IRC 1(g)", 2025: 2_700, 2026: 2_700},
    "exemption_amount": {"desc": "Exemption amount (qualifying-relative gross income test)",
                         "source": "IRC 151(d)(5)(B)", 2025: 5_200, 2026: 5_300},
    # --- OBBBA "Schedule 1-A" deductions ----------------------
    "senior_deduction": {"desc": "Senior deduction per person 65+ (2025-2028)",
                         "source": "OBBBA sec. 70103; IRC 151(d)(5)(C)", 2025: 6_000, 2026: 6_000},
    "senior_phaseout_start": {"desc": "Senior deduction phase-out start (MAGI)",
                              "source": "IRC 151(d)(5)(C)",
                              2025: _by_status(75_000, 150_000, 0, 75_000),
                              2026: _by_status(75_000, 150_000, 0, 75_000)},
    "senior_phaseout_rate": {"desc": "Senior deduction phase-out rate", "source": "IRC 151(d)(5)(C)",
                             2025: 0.06, 2026: 0.06},
    "tips_max": {"desc": "Qualified tips deduction cap (2025-2028)", "source": "OBBBA sec. 70201; IRC 224",
                 2025: 25_000, 2026: 25_000},
    "overtime_max": {"desc": "Qualified overtime deduction cap (2025-2028)",
                     "source": "OBBBA sec. 70202; IRC 225",
                     2025: _by_status(12_500, 25_000, 0, 12_500),
                     2026: _by_status(12_500, 25_000, 0, 12_500)},
    "tips_ot_phaseout_start": {"desc": "Tips/overtime phase-out start (MAGI)", "source": "IRC 224/225",
                               2025: _by_status(150_000, 300_000, 0, 150_000),
                               2026: _by_status(150_000, 300_000, 0, 150_000)},
    "tips_ot_phaseout_per_1000": {"desc": "Tips/overtime reduction per $1,000 over", "source": "IRC 224/225",
                                  2025: 100, 2026: 100},
    "car_interest_max": {"desc": "Qualified passenger vehicle loan interest cap",
                         "source": "OBBBA sec. 70203; IRC 163(h)(4)", 2025: 10_000, 2026: 10_000},
    "car_interest_phaseout_start": {"desc": "Car loan interest phase-out start (MAGI)",
                                    "source": "IRC 163(h)(4)",
                                    2025: _by_status(100_000, 200_000, 100_000, 100_000),
                                    2026: _by_status(100_000, 200_000, 100_000, 100_000)},
    "car_interest_phaseout_per_1000": {"desc": "Car loan interest reduction per $1,000 over",
                                       "source": "IRC 163(h)(4)", 2025: 200, 2026: 200},
    "nonitemizer_charity": {"desc": "Charitable deduction for non-itemizers (2026+)",
                            "source": "OBBBA sec. 70424; IRC 170(p)",
                            2025: _by_status(0, 0, 0, 0), 2026: _by_status(1_000, 2_000, 1_000, 1_000)},
    # --- Payroll / SE tax --------------------------------------
    "ss_wage_base": {"desc": "Social Security wage base", "source": "SSA COLA announcement",
                     2025: 176_100, 2026: 184_500},
    "ss_rate": {"desc": "Social Security rate (each of employee/employer)", "source": "IRC 3101/3111",
                2025: 0.062, 2026: 0.062},
    "medicare_rate": {"desc": "Medicare rate (each of employee/employer)", "source": "IRC 3101/3111",
                      2025: 0.0145, 2026: 0.0145},
    "se_factor": {"desc": "SE earnings factor (1 - 7.65%)", "source": "IRC 1402(a)(12)",
                  2025: 0.9235, 2026: 0.9235},
    "addl_medicare_rate": {"desc": "Additional Medicare tax rate", "source": "IRC 3101(b)(2)",
                           2025: 0.009, 2026: 0.009},
    "addl_medicare_threshold": {"desc": "Additional Medicare tax threshold (Form 8959; QSS uses $200K)",
                                "source": "IRC 3101(b)(2); Form 8959 instructions",
                                2025: _by_status(200_000, 250_000, 125_000, 200_000, 200_000),
                                2026: _by_status(200_000, 250_000, 125_000, 200_000, 200_000)},
    "niit_threshold": {"desc": "Net investment income tax threshold (Form 8960; QSS uses $250K)",
                       "source": "IRC 1411(b); Form 8960 instructions",
                       2025: _by_status(200_000, 250_000, 125_000, 200_000, 250_000),
                       2026: _by_status(200_000, 250_000, 125_000, 200_000, 250_000)},
    "niit_rate": {"desc": "Net investment income tax rate", "source": "IRC 1411", 2025: 0.038, 2026: 0.038},
    "sli_max": {"desc": "Student loan interest deduction cap", "source": "IRC 221(b)(1)", 2025: 2_500, 2026: 2_500},
    "sli_phase_start": {"desc": "Student loan interest phase-out start (MAGI; MFS not allowed)",
                        "source": "IRC 221(b)(2); Rev. Proc. 2024-40 / 2025-32 sec. 4.29",
                        2025: _by_status(85_000, 170_000, 0, 85_000, 85_000),
                        2026: _by_status(85_000, 175_000, 0, 85_000, 85_000)},
    "sli_phase_range": {"desc": "Student loan interest phase-out range", "source": "IRC 221(b)(2)",
                        2025: _by_status(15_000, 30_000, 1, 15_000, 15_000),
                        2026: _by_status(15_000, 30_000, 1, 15_000, 15_000)},
    "itemized_limit_2_37": {"desc": "Sec. 68 limitation on itemized deductions (2/37 for the 37% bracket, 2026+)",
                            "source": "IRC 68 as amended by OBBBA sec. 70111", 2025: 0, 2026: 1},
    # --- Estimated tax (IRC 6654) --------------------------------------------
    "est_current_year_pct": {"desc": "Safe harbor: % of current-year tax", "source": "IRC 6654(d)(1)(B)(i)",
                             2025: 0.90, 2026: 0.90},
    "est_prior_year_pct": {"desc": "Safe harbor: % of prior-year tax (AGI at or below threshold)",
                           "source": "IRC 6654(d)(1)(B)(ii)", 2025: 1.00, 2026: 1.00},
    "est_prior_year_pct_high": {"desc": "Safe harbor: % of prior-year tax when prior AGI exceeds the threshold",
                                "source": "IRC 6654(d)(1)(C)", 2025: 1.10, 2026: 1.10},
    "est_high_agi_threshold": {"desc": "Prior-year AGI above which the 110% rule applies (not indexed)",
                               "source": "IRC 6654(d)(1)(C)(ii)",
                               2025: _by_status(150_000, 150_000, 75_000, 150_000),
                               2026: _by_status(150_000, 150_000, 75_000, 150_000)},
    "est_min_balance": {"desc": "No penalty if tax after withholding is under this", "source": "IRC 6654(e)(1)",
                        2025: 1_000, 2026: 1_000},
    "est_farmer_pct": {"desc": "Farmers/fishermen: % of current-year tax", "source": "IRC 6654(i)(1)(A)",
                       2025: 2 / 3, 2026: 2 / 3},
    # --- Credits ---------------------------------------------------
    "ctc_per_child": {"desc": "Child tax credit per qualifying child under 17",
                      "source": "OBBBA sec. 70104; IRC 24(h)", 2025: 2_200, 2026: 2_200},
    "ctc_refundable": {"desc": "Refundable (ACTC) portion per child", "source": "IRC 24(d), Rev. Proc. 2025-32",
                       2025: 1_700, 2026: 1_700},
    "odc_per_dependent": {"desc": "Credit for other dependents", "source": "IRC 24(h)(4)",
                          2025: 500, 2026: 500},
    "ctc_phaseout_start": {"desc": "CTC phase-out start (MAGI)", "source": "IRC 24(h)(3)",
                           2025: _by_status(200_000, 400_000, 200_000, 200_000, 200_000),
                           2026: _by_status(200_000, 400_000, 200_000, 200_000, 200_000)},
    # --- Itemized deductions --------------------------------------
    "medical_floor": {"desc": "Medical expense AGI floor", "source": "IRC 213(a)", 2025: 0.075, 2026: 0.075},
    "salt_cap": {"desc": "SALT deduction cap", "source": "OBBBA sec. 70120; IRC 164(b)(7)",
                 2025: _by_status(40_000, 40_000, 20_000, 40_000),
                 2026: _by_status(40_400, 40_400, 20_200, 40_400)},
    "salt_phase_start": {"desc": "SALT cap phase-down start (MAGI)", "source": "IRC 164(b)(7)",
                         2025: _by_status(500_000, 500_000, 250_000, 500_000),
                         2026: _by_status(505_000, 505_000, 252_500, 505_000)},
    "salt_phase_rate": {"desc": "SALT cap phase-down rate", "source": "IRC 164(b)(7)", 2025: 0.30, 2026: 0.30},
    "salt_floor": {"desc": "SALT cap floor after phase-down", "source": "IRC 164(b)(7)",
                   2025: _by_status(10_000, 10_000, 5_000, 10_000),
                   2026: _by_status(10_000, 10_000, 5_000, 10_000)},
    "mortgage_limit": {"desc": "Acquisition debt limit (post-12/15/2017 loans)", "source": "IRC 163(h)(3)(F)",
                       2025: _by_status(750_000, 750_000, 375_000, 750_000),
                       2026: _by_status(750_000, 750_000, 375_000, 750_000)},
    "charity_floor_pct": {"desc": "Charitable deduction floor (% of AGI, itemizers, 2026+)",
                          "source": "OBBBA sec. 70425; IRC 170(b)(1)(I)", 2025: 0.0, 2026: 0.005},
    "charity_cash_public_pct": {"desc": "Cash to public charity limit (% AGI)", "source": "IRC 170(b)(1)(G)",
                                2025: 0.60, 2026: 0.60},
    "charity_property_public_pct": {"desc": "LTCG property to public charity limit (% AGI)",
                                    "source": "IRC 170(b)(1)(C)", 2025: 0.30, 2026: 0.30},
    "charity_cash_private_pct": {"desc": "Cash to private non-operating foundation (% AGI)",
                                 "source": "IRC 170(b)(1)(B)", 2025: 0.30, 2026: 0.30},
    "charity_property_private_pct": {"desc": "LTCG property to private foundation (% AGI)",
                                     "source": "IRC 170(b)(1)(D)", 2025: 0.20, 2026: 0.20},
    "gambling_loss_pct": {"desc": "Share of gambling losses deductible (capped at winnings)",
                          "source": "OBBBA sec. 70114; IRC 165(d)", 2025: 1.00, 2026: 0.90},
    "casualty_per_event": {"desc": "Personal casualty loss reduction per event", "source": "IRC 165(h)(1)",
                           2025: 100, 2026: 100},
    "casualty_agi_pct": {"desc": "Personal casualty loss AGI floor", "source": "IRC 165(h)(2)",
                         2025: 0.10, 2026: 0.10},
    # --- Capital gains / property --------------------------------
    "cap_loss_limit": {"desc": "Net capital loss deductible against ordinary income",
                       "source": "IRC 1211(b)", 2025: _by_status(3_000, 3_000, 1_500, 3_000),
                       2026: _by_status(3_000, 3_000, 1_500, 3_000)},
    "home_sale_exclusion": {"desc": "Sec. 121 principal residence gain exclusion", "source": "IRC 121(b)",
                            2025: _by_status(250_000, 500_000, 250_000, 250_000, 250_000),
                            2026: _by_status(250_000, 500_000, 250_000, 250_000, 250_000)},
    "collectibles_rate": {"desc": "Max rate on 28% rate gain (collectibles)", "source": "IRC 1(h)(4)",
                          2025: 0.28, 2026: 0.28},
    "unrecap_1250_rate": {"desc": "Max rate on unrecaptured Sec. 1250 gain", "source": "IRC 1(h)(1)(E)",
                          2025: 0.25, 2026: 0.25},
    # --- Losses -----------------------------------------------------
    "ebl_threshold": {"desc": "Excess business loss threshold", "source": "IRC 461(l); OBBBA sec. 70601",
                      2025: _by_status(313_000, 626_000, 313_000, 313_000),
                      2026: _by_status(256_000, 512_000, 256_000, 256_000)},
    "nol_pct_limit": {"desc": "NOL deduction limit (% of taxable income before NOL)",
                      "source": "IRC 172(a)(2)", 2025: 0.80, 2026: 0.80},
    # --- Business / depreciation --------------------------------
    "sec179_limit": {"desc": "Sec. 179 expensing limit", "source": "OBBBA sec. 70306; Rev. Proc. 2025-32",
                     2025: 2_500_000, 2026: 2_560_000},
    "sec179_phaseout": {"desc": "Sec. 179 phase-out threshold (property placed in service)",
                        "source": "IRC 179(b)(2)", 2025: 4_000_000, 2026: 4_090_000},
    "bonus_pct": {"desc": "Bonus depreciation % (property acquired after 1/19/2025)",
                  "source": "OBBBA sec. 70301; IRC 168(k)", 2025: 1.00, 2026: 1.00},
    "startup_deduction": {"desc": "Start-up / organizational cost immediate deduction",
                          "source": "IRC 195(b), 248", 2025: 5_000, 2026: 5_000},
    "startup_phaseout": {"desc": "Start-up cost phase-out threshold", "source": "IRC 195(b)",
                         2025: 50_000, 2026: 50_000},
    "qbi_rate": {"desc": "QBI deduction rate", "source": "IRC 199A", 2025: 0.20, 2026: 0.20},
    "qbi_phase_range": {"desc": "Sec. 199A phase-in range above the threshold", "source": "IRC 199A(b)(3); OBBBA sec. 70105",
                        2025: _by_status(50_000, 100_000, 50_000, 50_000),
                        2026: _by_status(75_000, 150_000, 75_000, 75_000)},
    "qbi_min_deduction": {"desc": "Sec. 199A minimum deduction (active QBI >= $1,000; 2026+)",
                          "source": "IRC 199A(i) as added by OBBBA sec. 70105", 2025: 0, 2026: 400},
    "qbi_min_qbi": {"desc": "Active QBI needed for the minimum deduction", "source": "IRC 199A(i)", 2025: 1_000, 2026: 1_000},
    "qbi_threshold": {"desc": "QBI threshold (wage/SSTB limits start above this)",
                      "source": "IRC 199A(e)(2); Rev. Proc. 2025-32",
                      2025: _by_status(197_300, 394_600, 197_300, 197_300),
                      2026: _by_status(201_750, 403_500, 201_775, 201_750)},
    "mileage_business": {"desc": "Standard mileage rate - business ($/mile)", "source": "IRS Notice",
                         2025: 0.70, 2026: 0.725},
    "mileage_medical": {"desc": "Standard mileage rate - medical/moving ($/mile)", "source": "IRS Notice",
                        2025: 0.21, 2026: 0.205},
    "mileage_charity": {"desc": "Standard mileage rate - charity ($/mile, statutory)", "source": "IRC 170(i)",
                        2025: 0.14, 2026: 0.14},
    "corp_rate": {"desc": "C corporation income tax rate", "source": "IRC 11(b)", 2025: 0.21, 2026: 0.21},
    "corp_charity_limit": {"desc": "Corporate charitable deduction limit (% of TI)", "source": "IRC 170(b)(2)",
                           2025: 0.10, 2026: 0.10},
    "corp_charity_floor": {"desc": "Corporate charitable floor (% of TI, 2026+)",
                           "source": "OBBBA sec. 70426", 2025: 0.0, 2026: 0.01},
    # --- Retirement ------------------------------------------------
    "ira_limit": {"desc": "IRA contribution limit", "source": "IRC 219(b)(5)", 2025: 7_000, 2026: 7_500},
    "ira_catchup": {"desc": "IRA catch-up (age 50+)", "source": "IRC 219(b)(5)(B)", 2025: 1_000, 2026: 1_100},
    "ira_phase_start_covered": {"desc": "Trad. IRA deduction phase-out start - taxpayer covered by plan",
                                "source": "IRC 219(g)",
                                2025: _by_status(79_000, 126_000, 0, 79_000),
                                2026: _by_status(81_000, 129_000, 0, 81_000)},
    "ira_phase_range_covered": {"desc": "Trad. IRA phase-out range - covered",
                                "source": "IRC 219(g)",
                                2025: _by_status(10_000, 20_000, 10_000, 10_000),
                                2026: _by_status(10_000, 20_000, 10_000, 10_000)},
    "ira_phase_start_spouse": {"desc": "Trad. IRA phase-out start - only spouse covered (MFJ)",
                               "source": "IRC 219(g)(7)", 2025: 236_000, 2026: 242_000},
    "roth_phase_start": {"desc": "Roth IRA contribution phase-out start", "source": "IRC 408A(c)(3)",
                         2025: _by_status(150_000, 236_000, 0, 150_000),
                         2026: _by_status(153_000, 242_000, 0, 153_000)},
    "roth_phase_range": {"desc": "Roth IRA phase-out range", "source": "IRC 408A(c)(3)",
                         2025: _by_status(15_000, 10_000, 10_000, 15_000),
                         2026: _by_status(15_000, 10_000, 10_000, 15_000)},
    "k401_limit": {"desc": "401(k) elective deferral limit", "source": "IRC 402(g)", 2025: 23_500, 2026: 24_500},
    "k401_catchup": {"desc": "401(k) catch-up age 50+", "source": "IRC 414(v)", 2025: 7_500, 2026: 8_000},
    "k401_catchup_60_63": {"desc": "401(k) super catch-up age 60-63", "source": "IRC 414(v)(2)(E)",
                           2025: 11_250, 2026: 11_250},
    "dc_limit": {"desc": "Defined contribution / SEP annual addition limit", "source": "IRC 415(c)",
                 2025: 70_000, 2026: 72_000},
    "sep_pct_se": {"desc": "SEP deduction as % of net SE income (20% = 25% of comp)",
                   "source": "IRC 404(h)", 2025: 0.20, 2026: 0.20},
    # --- Exclusions / gifts -----------------------------------------
    "feie_limit": {"desc": "Foreign earned income exclusion", "source": "IRC 911(b)(2)",
                   2025: 130_000, 2026: 132_900},
    "gift_annual_exclusion": {"desc": "Gift tax annual exclusion per donee", "source": "IRC 2503(b)",
                              2025: 19_000, 2026: 19_000},
    "estate_exclusion": {"desc": "Basic exclusion amount (estate/gift)", "source": "OBBBA sec. 70106",
                         2025: 13_990_000, 2026: 15_000_000},
    "ltc_per_diem": {"desc": "Long-term care per diem limit ($/day) - verify 2026",
                     "source": "IRC 7702B(d); Rev. Proc. 2024-40 / 2025-32", 2025: 420, 2026: 430},
    "transit_monthly": {"desc": "Qualified transportation fringe (monthly)", "source": "IRC 132(f)",
                        2025: 325, 2026: 340},
    "gtl_exclusion": {"desc": "Group-term life coverage excluded", "source": "IRC 79(a)",
                      2025: 50_000, 2026: 50_000},
}


def param(key: str, year: int = DEFAULT_YEAR, status: str | None = None) -> float:
    """Look up a scalar parameter. Status-dependent ones require ``status``."""
    entry = PARAMS[key]
    value = entry[year]
    if isinstance(value, dict):
        if status is None:
            raise ValueError(f"Parameter {key!r} depends on filing status")
        return value[status if status in value else _status_key(status)]
    return value


def is_status_param(key: str) -> bool:
    return isinstance(PARAMS[key][YEARS[0]], dict)


# Group-term life Uniform Premium Table I (cost per $1,000 per month), Reg. 1.79-3.
GTL_TABLE: Tuple[Tuple[int, float], ...] = (
    (0, 0.05), (25, 0.06), (30, 0.08), (35, 0.09), (40, 0.10), (45, 0.15),
    (50, 0.23), (55, 0.43), (60, 0.66), (65, 1.27), (70, 2.06),
)

# The engine and workbook support two computation methods:
#   "simplified" - common hand-computation shortcuts: capital gains taxed band-by-band at the smaller
#                  of the ordinary and capital-gain rate, DRD at the pre-2018 70% / 80% / 100%,
#                  SEP = 20% of net SE income.
#   "law"        - the statutory computation (Schedule D Tax Worksheet, 50% / 65% / 100% DRD, SEP
#                  on net SE income less 1/2 SE tax).
METHODS = ("simplified", "law")
WORKBOOK_DEFAULT_METHOD = "law"

# Where the simplified method differs from the statute. The workbook follows these in Simplified mode.
SIMPLIFIED_METHODS: Tuple[Tuple[str, str], ...] = (
    ("Capital gains", "'Pick smaller': each band of LTCG/QD is taxed at the smaller of the ordinary and "
                      "capital-gain rate. Example ($400K LTCG, single 2026): $52,554.00. "
                      "Statute (Sch. D worksheet, IRC 1(h)): $52,582.50."),
    ("DRD (IRC 243)", "70% (<20% owned) / 80% (20%-<80%) / 100% (80%+), the pre-TCJA rates. "
                      "Statute since 2018: 50% / 65% / 100%."),
    ("SEP (IRC 404(h))", "20% of net self-employment income. Statute: 20% of (net SE income - 1/2 SE tax)."),
)
