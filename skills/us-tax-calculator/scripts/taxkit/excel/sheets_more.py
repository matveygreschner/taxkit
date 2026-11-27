"""All other calculator sheets. Each mirrors a Python module so the two can be
cross-checked by ``scripts/verify_workbook.py``."""
from __future__ import annotations

from .core import Calc

YES = '"Yes"'


def _phase(amount: str, magi: str, start: str, per1000: str) -> str:
    """MAX(0, amount - ROUNDUP(MAX(0,magi-start)/1000,0)*per1000)"""
    return f"MAX(0,{amount}-ROUNDUP(MAX(0,{magi}-{start})/1000,0)*{per1000})"


# ===================================================================== 1040 ==
def build_1040(wb, reg):
    c = Calc(wb, reg, "Form_1040", "Form 1040 - Full Return",
             "Individual tax formula. Itemized deductions come from the Sch_A sheet.")
    c.section("FILING")
    c.inp("status", "Filing status", "MFJ", "text", choices="status")
    c.inp("boxes", "Age 65+/blind boxes checked (0-4)", 0, "int")
    c.inp("seniors", "Number of people age 65+ (senior deduction)", 0, "int")
    c.inp("kids", "Qualifying children under 17 (CTC)", 2, "int")
    c.inp("others", "Other dependents ($500 credit)", 0, "int")
    c.section("INCOME")
    c.inp("wages", "Wages (W-2 box 1)", 150_000)
    c.inp("interest", "Taxable interest", 2_000)
    c.inp("odiv", "Ordinary dividends (incl. qualified)", 5_000)
    c.inp("qdiv", "  Qualified dividends", 4_000)
    c.inp("netcg", "Net capital gain/(loss) from Sch. D (loss max -3,000)", 10_000,
          note="Use the Capital sheet's netting section.")
    c.inp("ltcg", "  Net LTCG eligible for 0/15/20%", 10_000)
    c.inp("schc", "Schedule C net profit", 0)
    c.inp("se_w2", "  W-2 Social Security wages of the self-employed person", 0,
          note="On a joint return, only the self-employed spouse's own wages use up the SS wage base")
    c.inp("other", "Other income (unemployment, prizes, K-1, gambling...)", 0)
    c.inp("ss", "Taxable Social Security (Income_Items sheet)", 0)
    c.calc("gross", "GROSS INCOME", "{wages}+{interest}+{odiv}+{netcg}+{schc}+{other}+{ss}", total=True)
    c.section("ADJUSTMENTS (for AGI)")
    c.calc("nese", "SE earnings (Sch C x 92.35%)", "IF(MAX(0,{schc})*{P:se_factor}<400,0,MAX(0,{schc})*{P:se_factor})")
    c.calc("se_raw", "SE tax (unrounded)", "MIN({nese},MAX(0,{P:ss_wage_base}-{se_w2}))*{P:ss_rate}*2"
                                           "+{nese}*{P:medicare_rate}*2", note="Wages use up the SS wage base first.")
    c.calc("half_se", "Deductible half of SE tax", "ROUND({se_raw}/2,2)")
    c.inp("se_health", "Self-employed health insurance", 0)
    c.inp("se_ret", "Self-employed retirement (SEP/Keogh)", 0, note="Retirement sheet")
    c.inp("ira", "Deductible IRA contribution", 0, note="Retirement sheet")
    c.inp("sli", "Student loan interest (max $2,500)", 0)
    c.inp("educator", "Educator expenses (max $300)", 0)
    c.inp("alimony", "Alimony paid (pre-2019 decree)", 0)
    c.inp("other_adj", "Other adjustments", 0)
    c.calc("adj_other", "(helper) adjustments other than student loan interest",
           "{half_se}+{se_health}+{se_ret}+{ira}+MIN({educator},300)+{alimony}+{other_adj}")
    c.calc("sli_ok", "Student loan interest allowed (phase-out on MAGI; none MFS)",
           "IF({status}=\"MFS\",0,ROUND(MAX(0,MIN({sli},{P:sli_max})*(1-MAX(0,{gross}-{adj_other}"
           "-{PS:sli_phase_start:status})/{PS:sli_phase_range:status})),2))")
    c.calc("adj", "Total adjustments", "{adj_other}+{sli_ok}")
    c.calc("agi", "ADJUSTED GROSS INCOME", "{gross}-{adj}", total=True)
    c.section("DEDUCTIONS")
    c.calc("std", "Standard deduction", "{PS:std_deduction:status}+{boxes}*{PS:std_additional:status}")
    c.inp("tips", "Qualified tips", 0)
    c.inp("ot", "Qualified overtime premium", 0)
    c.inp("car", "Qualified car loan interest", 0)
    c.calc("senior", "Senior deduction (phased down per person)", "IF({status}=\"MFS\",0,ROUND({seniors}*MAX(0,"
           "{P:senior_deduction}-MAX(0,{agi}-{PS:senior_phaseout_start:status})*{P:senior_phaseout_rate}),2))")
    c.calc("tips_d", "No tax on tips", "IF({status}=\"MFS\",0," + _phase(
        "MIN({tips},{P:tips_max})", "{agi}", "{PS:tips_ot_phaseout_start:status}", "{P:tips_ot_phaseout_per_1000}") + ")")
    c.calc("ot_d", "No tax on overtime", "IF({status}=\"MFS\",0," + _phase(
        "MIN({ot},{PS:overtime_max:status})", "{agi}", "{PS:tips_ot_phaseout_start:status}",
        "{P:tips_ot_phaseout_per_1000}") + ")")
    c.calc("car_d", "Car loan interest", _phase("MIN({car},{P:car_interest_max})", "{agi}",
                                                "{PS:car_interest_phaseout_start:status}",
                                                "{P:car_interest_phaseout_per_1000}"))
    c.calc("sch1a_base", "(helper) Schedule 1-A before non-itemizer charity", "{senior}+{tips_d}+{ot_d}+{car_d}")
    c.calc("item_raw", "Itemized deductions (Sch_A)", "{Sch_A.total}")
    c.calc("top37", "(helper) start of 37% bracket",
           "SUMIFS(Brackets!$D$%d:$D$%d,Brackets!$A$%d:$A$%d,{YEAR},Brackets!$B$%d:$B$%d,{status},"
           "Brackets!$C$%d:$C$%d,7)" % ((reg.ord_rows[0], reg.ord_rows[1]) * 4), "money0")
    c.calc("sec68", "Sec. 68 reduction (2/37, 2026+)", "ROUND({P:itemized_limit_2_37}*2/37*MIN(MAX(0,{item_raw}),"
                                                     "MAX(0,{agi}-{sch1a_base}-{top37})),2)")
    c.calc("item", "Itemized deductions allowed", "{item_raw}-{sec68}")
    c.calc("use_item", "Itemize? (1 = yes)", "IF({item}>{std},1,0)", "int")
    c.calc("ded", "Deduction used", "IF({use_item}=1,{item},{std})")
    c.calc("nonitem", "Non-itemizer charity (2026+)",
           "IF({use_item}=1,0,MIN({Sch_A.cash_pub},{PS:nonitemizer_charity:status}))")
    c.calc("sch1a", "Schedule 1-A + other below-the-line", "{sch1a_base}+{nonitem}")
    c.calc("ti_bq", "Taxable income before QBI", "MAX(0,{agi}-{ded}-{sch1a})")
    c.inp("other_qbi", "Other QBI (K-1s)", 0)
    c.calc("qbi_amt", "Qualified business income (net; losses offset)",
           "IF({schc}>0,{schc}-{half_se}-{se_health}-{se_ret},{schc})+{other_qbi}")
    c.calc("qbi", "QBI deduction (at/below threshold; 2026+ $400 minimum)",
           "IF({qbi_amt}<=0,0,ROUND(MAX(MAX(0,MIN({P:qbi_rate}*{qbi_amt},{P:qbi_rate}*MAX(0,{ti_bq}-{qdiv}"
           "-MAX(0,{ltcg})))),IF({qbi_amt}>={P:qbi_min_qbi},{P:qbi_min_deduction},0)),2))",
           note="Above the threshold, W-2 wage / UBIA / SSTB limits apply - use the engine's qbi_deduction_full.")
    c.calc("ti", "TAXABLE INCOME", "MAX(0,{ti_bq}-{qbi})", total=True)
    c.section("TAX")
    c.calc("pref", "Preferential income", "MIN({ti},{qdiv}+MAX(0,{ltcg}))")
    c.calc("ord", "Ordinary portion", "{ti}-{pref}")
    c.calc("tax_law", "Income tax - law (Sch. D worksheet)",
           "ROUND(MIN({TAX:ti:status},{TAX:ord:status}+{CGT:ti:status}-{CGT:ord:status}),2)")
    c.calc("tax_simplified", "Income tax - simplified 'pick smaller'",
           "ROUND(MIN({TAX:ti:status},{TAX:ord:status}+{MINT:ti:status}-{MINT:ord:status}),2)")
    c.calc("tax", "Income tax (method on Start)", "IF({METHOD}=\"Law\",{tax_law},{tax_simplified})")
    c.calc("se", "Self-employment tax", "ROUND({se_raw},2)")
    c.calc("addl_med", "Additional Medicare tax (0.9%)",
           "ROUND(MAX(0,{nese}-MAX(0,{PS:addl_medicare_threshold:status}-{wages}))*{P:addl_medicare_rate},2)"
           "+MAX(0,{wages}-{PS:addl_medicare_threshold:status})*{P:addl_medicare_rate}")
    c.inp("nii", "Net investment income (for NIIT)", 0)
    c.calc("niit", "Net investment income tax (3.8%)",
           "ROUND(MIN(MAX(0,{nii}),MAX(0,{agi}-{PS:niit_threshold:status}))*{P:niit_rate},2)")
    c.calc("before", "Tax before credits", "{tax}+{se}+{addl_med}+{niit}")
    c.section("CREDITS & PAYMENTS")
    c.calc("ctc_tent", "CTC + ODC before phase-out", "{kids}*{P:ctc_per_child}+{others}*{P:odc_per_dependent}")
    c.calc("ctc_allow", "After phase-out ($50 per $1,000)", _phase("{ctc_tent}", "{agi}",
                                                                   "{PS:ctc_phaseout_start:status}", "50"))
    c.calc("ctc_nonref", "Nonrefundable portion used", "MIN({ctc_allow},MAX(0,{tax}))")
    c.inp("eitc", "EITC claimed (not computed)", 0)
    c.calc("payroll_paid", "(helper) employee SS + Medicare + Addl Medicare + 1/2 SE tax",
           "{P:ss_rate}*MIN({wages},{P:ss_wage_base})+{P:medicare_rate}*{wages}+MAX(0,{wages}"
           "-{PS:addl_medicare_threshold:status})*{P:addl_medicare_rate}+{half_se}")
    c.calc("actc", "Refundable ACTC (3+ children: Sch. 8812 Part II-B alternative)",
           "MAX(0,MIN({ctc_allow}-{ctc_nonref},{kids}*{P:ctc_refundable},MAX(MAX(0,0.15*({wages}+{schc}-{half_se}-2500)),"
           "IF({kids}>=3,MAX(0,{payroll_paid}-{eitc}),0))))")
    c.inp("other_cr", "Other nonrefundable credits", 0)
    c.calc("nonref", "Total nonrefundable credits", "MIN({tax},{ctc_nonref}+{other_cr})")
    c.calc("total_tax", "TOTAL TAX", "{before}-{nonref}", total=True)
    c.inp("withheld", "Federal withholding", 18_000)
    c.inp("estimates", "Estimated payments", 0)
    c.calc("payments", "Payments + refundable credits", "{withheld}+{estimates}+{actc}")
    c.calc("balance", "BALANCE DUE / (REFUND)", "{total_tax}-{payments}", total=True)
    c.calc("eff", "Effective rate on AGI", "IF({agi}>0,{total_tax}/{agi},0)", "pct")
    return c


# ==================================================================== SCH A ==
def build_sch_a(wb, reg):
    c = Calc(wb, reg, "Sch_A", "Schedule A - Itemized Deductions", "IRC 163, 164, 170, 213. 2026 OBBBA rules.")
    c.section("LINKED FROM FORM 1040 (overwrite to use standalone)")
    c.calc("status", "Filing status", "{Form_1040.status}", "text")
    c.calc("agi", "AGI (also used as MAGI)", "{Form_1040.agi}")
    c.section("MEDICAL (7.5% floor)")
    c.inp("med", "Unreimbursed medical & dental", 0)
    c.calc("med_d", "Medical deduction", "ROUND(MAX(0,{med}-{P:medical_floor}*MAX(0,{agi})),2)")
    c.section("STATE & LOCAL TAXES (SALT cap)")
    c.inp("salt", "State/local income (or sales) + property taxes paid", 18_000)
    c.calc("salt_cap", "SALT cap after phase-down (MFS: half rate)", "MAX({PS:salt_floor:status},{PS:salt_cap:status}"
           "-{P:salt_phase_rate}*IF({status}=\"MFS\",0.5,1)*MAX(0,{agi}-{PS:salt_phase_start:status}))")
    c.calc("salt_d", "SALT deduction", "ROUND(MIN({salt},{salt_cap}),2)")
    c.section("INTEREST")
    c.inp("mort", "Home mortgage interest", 14_000)
    c.inp("bal", "Average acquisition debt balance", 400_000)
    c.calc("mort_lim", "Debt limit ($750K / $375K MFS)", "{PS:mortgage_limit:status}")
    c.calc("mort_d", "Mortgage interest deduction", "ROUND(IF(OR({bal}<={mort_lim},{bal}<=0),{mort},"
                                                    "{mort}*{mort_lim}/{bal}),2)")
    c.inp("inv_int", "Investment interest expense", 0)
    c.inp("nii", "Net investment income", 0)
    c.calc("inv_d", "Investment interest deduction", "ROUND(MIN({inv_int},MAX(0,{nii})),2)")
    c.calc("inv_cf", "Investment interest carryforward", "{inv_int}-{inv_d}")
    c.section("CHARITY")
    c.inp("cash_pub", "Cash to public charities (60%)", 3_000)
    c.inp("prop_pub", "LTCG property to public charities - FMV (30%)", 0,
          note="Short-term / ordinary property: enter basis instead.")
    c.inp("cash_priv", "Cash to private non-operating foundations (30%)", 0)
    c.inp("prop_priv", "LTCG property to private foundations (20%)", 0)
    c.calc("agi0", "(helper) AGI floored at zero", "MAX(0,{agi})")
    c.calc("ch_allowed", "Allowed before floor", "MIN(MIN({cash_pub},{P:charity_cash_public_pct}*{agi0})"
           "+MIN({prop_pub},{P:charity_property_public_pct}*{agi0})+MIN({cash_priv},{P:charity_cash_private_pct}*{agi0})"
           "+MIN({prop_priv},{P:charity_property_private_pct}*{agi0}),{P:charity_cash_public_pct}*{agi0})")
    c.calc("ch_floor", "0.5%-of-AGI floor (2026+)", "{P:charity_floor_pct}*{agi0}")
    c.calc("ch_d", "Charitable deduction", "ROUND(MAX(0,{ch_allowed}-{ch_floor}),2)")
    c.calc("ch_cf", "Carryforward (5 years)", "{cash_pub}+{prop_pub}+{cash_priv}+{prop_priv}-{ch_allowed}")
    c.section("OTHER")
    c.inp("casualty", "Casualty loss allowed (Losses sheet)", 0)
    c.inp("gamb_l", "Gambling losses", 0)
    c.inp("gamb_w", "Gambling winnings (reported as income)", 0)
    c.calc("gamb_d", "Gambling loss deduction (90% in 2026)", "ROUND(MIN({gamb_l}*{P:gambling_loss_pct},{gamb_w}),2)")
    c.inp("other_i", "Other itemized (IRD estate tax, claim of right...)", 0)
    c.calc("total", "TOTAL ITEMIZED DEDUCTIONS",
           "{med_d}+{salt_d}+{mort_d}+{inv_d}+{ch_d}+{casualty}+{gamb_d}+{other_i}", total=True)
    c.calc("std_cmp", "Standard deduction (for comparison)", "{Form_1040.std}")
    return c


# ================================================================== PAYROLL ==
def build_payroll(wb, reg):
    c = Calc(wb, reg, "Payroll_SE", "Payroll, Self-Employment Tax & NIIT", "IRC 1401, 1411, 3101, 3111.")
    c.inp("status", "Filing status", "MFJ", "text", choices="status")
    c.section("FICA ON WAGES (one employee)")
    c.inp("wages", "Employee wages", 275_000)
    c.inp("spouse_w", "Spouse's wages (for 0.9% threshold)", 0)
    c.calc("ss", "Social Security 6.2% (each side, up to wage base)", "ROUND(MIN({wages},{P:ss_wage_base})*{P:ss_rate},2)")
    c.calc("med", "Medicare 1.45% (each side, no cap)", "ROUND({wages}*{P:medicare_rate},2)")
    c.calc("er_total", "EMPLOYER FICA (deductible by employer)", "{ss}+{med}", total=True)
    c.calc("ee_total", "Employee FICA withheld", "{ss}+{med}")
    c.calc("addl", "Additional Medicare tax 0.9% (employee only)", "ROUND(MAX(0,{wages}+{spouse_w}"
                                                                    "-{PS:addl_medicare_threshold:status})*{P:addl_medicare_rate},2)",
           total=True)
    c.section("SELF-EMPLOYMENT TAX (Schedule SE)")
    c.inp("se_inc", "Net self-employment income (Sch C / GP / K-1 SE)", 275_000)
    c.inp("se_w2", "W-2 wages of the same person", 0)
    c.calc("nese", "Net earnings from SE (x 92.35%)", "IF(MAX(0,{se_inc})*{P:se_factor}<400,0,MAX(0,{se_inc})*{P:se_factor})")
    c.calc("se_ss", "Social Security portion 12.4%", "ROUND(MIN({nese},MAX(0,{P:ss_wage_base}-{se_w2}))*{P:ss_rate}*2,2)")
    c.calc("se_med", "Medicare portion 2.9%", "ROUND({nese}*{P:medicare_rate}*2,2)")
    c.calc("se_tax", "SE TAX", "ROUND(MIN({nese},MAX(0,{P:ss_wage_base}-{se_w2}))*{P:ss_rate}*2+{nese}*{P:medicare_rate}*2,2)",
           total=True)
    c.calc("se_half", "Above-the-line deduction (1/2 SE tax)", "ROUND({se_tax}/2,2)", total=True)
    c.calc("se_addl", "Additional Medicare on SE earnings", "ROUND(MAX(0,{nese}-MAX(0,{PS:addl_medicare_threshold:status}"
                                                            "-{se_w2}))*{P:addl_medicare_rate},2)")
    c.section("NET INVESTMENT INCOME TAX")
    c.inp("nii", "Net investment income", 50_000)
    c.inp("magi", "MAGI", 300_000)
    c.calc("niit", "NIIT 3.8% x lesser of NII or MAGI over threshold",
           "ROUND(MIN(MAX(0,{nii}),MAX(0,{magi}-{PS:niit_threshold:status}))*{P:niit_rate},2)", total=True)
    return c


# ============================================================ STD / CREDITS ==
def build_std_credits(wb, reg):
    c = Calc(wb, reg, "Std_Ded_Credits", "Standard Deduction, Dependents, Kiddie Tax, Credits, Sch. 1-A",
             "IRC 1(g), 24, 63, 224, 225.")
    c.calc("s_single", "(helper) single status code", '"S"', "text")
    c.section("STANDARD DEDUCTION")
    c.inp("status", "Filing status", "S", "text", choices="status")
    c.inp("boxes", "Age 65+/blind boxes", 0, "int")
    c.inp("is_dep", "Claimed as a dependent?", "Yes", "text", choices="yesno")
    c.inp("earned", "Earned income (if dependent)", 7_600)
    c.inp("mfs_item", "MFS and spouse itemizes?", "No", "text", choices="yesno")
    c.calc("basic", "Basic standard deduction", "{PS:std_deduction:status}")
    c.calc("std", "STANDARD DEDUCTION", "IF(AND({status}=\"MFS\",{mfs_item}=" + YES + "),0,IF({is_dep}=" + YES +
           ",MIN({basic},MAX({P:dep_std_min},{earned}+{P:dep_std_earned_addon})),{basic})"
           "+{boxes}*{PS:std_additional:status})", total=True)
    c.section("KIDDIE TAX (Form 8615, simplified)")
    c.inp("k_earned", "Child's earned income", 0)
    c.inp("k_unearned", "Child's unearned income (interest, dividends, gains)", 10_000)
    c.inp("p_ti", "Parents' taxable income", 200_000)
    c.inp("p_status", "Parents' filing status", "MFJ", "text", choices="status")
    c.calc("k_std", "Child's standard deduction", "MIN({PS:std_deduction:s_single},MAX({P:dep_std_min},"
                                                 "{k_earned}+{P:dep_std_earned_addon}))")
    c.calc("k_ti", "Child's taxable income", "MAX(0,{k_earned}+{k_unearned}-{k_std})")
    c.calc("k_nui", "Net unearned income (over $2,700)", "MIN({k_ti},MAX(0,{k_unearned}-{P:kiddie_threshold}))")
    c.calc("k_p_plus", "(helper) parents TI + NUI", "{p_ti}+{k_nui}")
    c.calc("k_rest", "(helper) child TI - NUI", "{k_ti}-{k_nui}")
    c.calc("k_parent_tax", "Tax on NUI at parents' rate", "ROUND({TAX:k_p_plus:p_status},2)-ROUND({TAX:p_ti:p_status},2)")
    c.calc("k_child_tax", "Tax on the rest at child's rate", "ROUND({TAX:k_rest:s_single},2)")
    c.calc("k_total", "CHILD'S TOTAL TAX", "{k_parent_tax}+{k_child_tax}", total=True)
    c.calc("k_alone", "Tax if kiddie tax did not apply", "ROUND({TAX:k_ti:s_single},2)")
    c.section("CHILD TAX CREDIT / CREDIT FOR OTHER DEPENDENTS")
    c.inp("c_status", "Filing status", "MFJ", "text", choices="status")
    c.inp("c_kids", "Qualifying children under 17", 2, "int")
    c.inp("c_others", "Other dependents", 1, "int")
    c.inp("c_magi", "MAGI", 100_000)
    c.inp("c_tax", "Tax before credits", 10_000)
    c.inp("c_earned", "Earned income", 100_000)
    c.calc("c_tent", "Tentative credit", "{c_kids}*{P:ctc_per_child}+{c_others}*{P:odc_per_dependent}")
    c.calc("c_allow", "After phase-out", _phase("{c_tent}", "{c_magi}", "{PS:ctc_phaseout_start:c_status}", "50"))
    c.calc("c_nonref", "Nonrefundable used", "MIN({c_allow},MAX(0,{c_tax}))", total=True)
    c.inp("c_payroll", "Employee SS/Medicare + 1/2 SE tax paid (3+ children method)", 0)
    c.inp("c_eitc", "EITC claimed", 0)
    c.calc("c_actc", "Refundable ACTC", "MAX(0,MIN({c_allow}-{c_nonref},{c_kids}*{P:ctc_refundable},"
           "MAX(MAX(0,0.15*({c_earned}-2500)),IF({c_kids}>=3,MAX(0,{c_payroll}-{c_eitc}),0))))", total=True)
    c.section("SCHEDULE 1-A (OBBBA 2025-2028)")
    c.inp("o_status", "Filing status", "S", "text", choices="status")
    c.inp("o_magi", "MAGI", 100_000)
    c.inp("o_seniors", "People age 65+", 1, "int")
    c.inp("o_tips", "Qualified tips", 30_000)
    c.inp("o_ot", "Qualified overtime premium", 20_000)
    c.inp("o_car", "Car loan interest (new U.S.-assembled vehicle)", 5_000)
    c.calc("o_senior", "Senior deduction (per person)", "IF({o_status}=\"MFS\",0,ROUND({o_seniors}*MAX(0,"
           "{P:senior_deduction}-MAX(0,{o_magi}-{PS:senior_phaseout_start:o_status})*{P:senior_phaseout_rate}),2))")
    c.calc("o_tips_d", "Tips deduction", "IF({o_status}=\"MFS\",0," + _phase(
        "MIN({o_tips},{P:tips_max})", "{o_magi}", "{PS:tips_ot_phaseout_start:o_status}",
        "{P:tips_ot_phaseout_per_1000}") + ")")
    c.calc("o_ot_d", "Overtime deduction", "IF({o_status}=\"MFS\",0," + _phase(
        "MIN({o_ot},{PS:overtime_max:o_status})", "{o_magi}", "{PS:tips_ot_phaseout_start:o_status}",
        "{P:tips_ot_phaseout_per_1000}") + ")")
    c.calc("o_car_d", "Car loan interest deduction", _phase("MIN({o_car},{P:car_interest_max})", "{o_magi}",
                                                            "{PS:car_interest_phaseout_start:o_status}",
                                                            "{P:car_interest_phaseout_per_1000}"))
    c.calc("o_total", "TOTAL SCHEDULE 1-A", "{o_senior}+{o_tips_d}+{o_ot_d}+{o_car_d}", total=True)
    return c


# ================================================================== CAPITAL ==
def build_capital(wb, reg):
    c = Calc(wb, reg, "Capital", "Property Transactions & Capital Gains", "IRC 1001, 1012, 1016, 121, 1211, 1212.")
    c.section("AMOUNT REALIZED")
    c.inp("cash", "Money received", 1_500_000)
    c.inp("fmv", "FMV of property received", 2_500_000)
    c.inp("debt", "Debt relief (buyer assumes mortgage)", 500_000)
    c.inp("sell", "Selling expenses", 45_000)
    c.calc("ar", "AMOUNT REALIZED", "{cash}+{fmv}+{debt}-{sell}", total=True)
    c.section("ADJUSTED BASIS")
    c.inp("cost", "Original cost", 200_000)
    c.inp("improve", "Capital improvements (NOT repairs)", 200_000)
    c.inp("deprec", "Depreciation / cost recovery taken", 55_000)
    c.calc("ab", "ADJUSTED BASIS", "{cost}+{improve}-{deprec}", total=True)
    c.section("GAIN")
    c.calc("realized", "Realized gain/(loss)", "{ar}-{ab}")
    c.inp("personal", "Personal-use asset?", "No", "text", choices="yesno")
    c.inp("use121", "Principal residence - apply Sec. 121?", "No", "text", choices="yesno")
    c.inp("h_status", "  Filing status", "MFJ", "text", choices="status")
    c.inp("h_own", "  Months owned (last 5 yrs)", 24, "int")
    c.inp("h_use", "  Months used as main home (last 5 yrs)", 24, "int")
    c.inp("h_partial", "  Health / job / unforeseen reason?", "No", "text", choices="yesno")
    c.calc("excl", "Sec. 121 exclusion available", "IF(MIN({h_own},{h_use})>=24,{PS:home_sale_exclusion:h_status},"
                                                   "IF({h_partial}=" + YES + ",ROUND({PS:home_sale_exclusion:h_status}"
                                                   "*MIN({h_own},{h_use})/24,2),0))")
    c.calc("recognized", "RECOGNIZED GAIN/(LOSS)", "IF(AND({realized}<0,{personal}=" + YES + "),0,IF(AND({realized}>0,"
                                                  "{use121}=" + YES + "),{realized}-MIN({realized},{excl}),{realized}))",
           total=True)
    c.section("CAPITAL GAIN NETTING (enter losses as positive numbers)")
    c.inp("n_status", "Filing status", "S", "text", choices="status")
    c.inp("stg", "Short-term gains", 0)
    c.inp("stl", "Short-term losses", 120_000)
    c.inp("ltg", "Long-term gains", 109_000)
    c.inp("ltl", "Long-term losses", 0)
    c.inp("st_co", "ST loss carryover from prior year", 0)
    c.inp("lt_co", "LT loss carryover from prior year", 0)
    c.inp("n_ti", "Taxable income (Form 1040 line 15, before the zero floor; may be negative)", 1_000_000,
          note="Only the part of the loss deduction that income absorbs reduces the carryover")
    c.calc("nst", "Net short-term", "{stg}-{stl}-{st_co}")
    c.calc("nlt", "Net long-term", "{ltg}-{ltl}-{lt_co}")
    c.calc("net", "Net capital gain/(loss)", "{nst}+{nlt}", total=True)
    c.calc("tx_st", "Taxable net ST gain (ordinary rates)", "IF({net}<0,0,IF({nst}<0,0,IF({nlt}>=0,{nst},{net})))")
    c.calc("tx_lt", "Taxable net LT gain (0/15/20%)", "IF({net}<0,0,IF({nlt}<0,0,IF({nst}>=0,{nlt},{net})))")
    c.calc("ded", "Loss deductible this year ($3,000 / $1,500 MFS)", "IF({net}<0,MIN(-{net},{PS:cap_loss_limit:n_status}),0)",
           total=True)
    c.calc("st_left", "(helper) ST loss remaining", "IF({net}>=0,0,IF({nlt}>=0,-{net},IF({nst}>=0,0,-{nst})))")
    c.calc("lt_left", "(helper) LT loss remaining", "IF({net}>=0,0,IF({nlt}>=0,0,IF({nst}>=0,-{net},-{nlt})))")
    c.calc("used", "(helper) loss deduction absorbed by income", "MIN({ded},MAX(0,{n_ti}+{ded}))")
    c.calc("st_cf", "ST loss carryforward", "MAX(0,{st_left}-{used})")
    c.calc("lt_cf", "LT loss carryforward", "{lt_left}-MAX(0,{used}-{st_left})")
    c.section("STOCK BASIS AFTER SPLIT / STOCK DIVIDEND")
    c.inp("sh", "Shares originally bought", 1_000, "num")
    c.inp("sh_basis", "Total cost", 100_000)
    c.inp("ratio", "New shares per old share (2-for-1 = 2; 10% stock div = 1.1)", 1.1, "factor")
    c.inp("sh_sold", "Shares sold", 1_100, "num")
    c.inp("price", "Sale price per share", 210)
    c.calc("sh_new", "Shares after", "{sh}*{ratio}", "num")
    c.calc("bps", "Basis per share", "{sh_basis}/{sh_new}")
    c.calc("sh_gain", "Gain/(loss) on shares sold", "{sh_sold}*({price}-{bps})", total=True)
    c.note("Cash dividends do not change basis.")
    c.section("FORECLOSURE / REPOSSESSION")
    c.inp("f_debt", "Outstanding loan", 60_000)
    c.inp("f_basis", "Adjusted basis", 10_000)
    c.inp("f_fmv", "FMV of property", 25_000)
    c.inp("f_rec", "Recourse loan?", "Yes", "text", choices="yesno")
    c.calc("f_gain", "Gain/(loss) on disposition", "IF({f_rec}=" + YES + ",{f_fmv}-{f_basis},{f_debt}-{f_basis})", total=True)
    c.calc("f_cod", "Cancellation of debt income", "IF({f_rec}=" + YES + ",MAX(0,{f_debt}-{f_fmv}),0)", total=True)
    return c


# ================================================================= ENTITIES ==
def build_entities(wb, reg):
    c = Calc(wb, reg, "Entities", "Business Entities - Owner Reporting & C Corp Tax", "IRC 11, 243, 701, 1366.",
             widths=(2, 46, 16, 16, 16, 16, 40))
    c.section("FACTS", "BCDEFG")
    c.inp("ni", "Book net income/(loss) AFTER deducting owner pay", -55_000)
    c.inp("pay", "Owner 'salary' deducted", 100_000)
    c.inp("dist", "Distributions / withdrawals / dividends to owner", 40_000)
    c.inp("pct", "Owner's share (partnership / S corp)", 0.5, "pct")
    c.inp("gp", "Partner is a general partner (or LP with management)?", "Yes", "text", choices="yesno")
    c.inp("basis_ok", "Owner has enough basis for distributions?", "Yes", "text", choices="yesno")
    c.gap()
    c.header_row(["Owner reports", "Sole prop / SMLLC", "Partnership", "S corp", "C corp", "Why"], 2)
    rows = [
        ("w2", "W-2 wages", "0", "0", "{pay}", "{pay}", "Only corporations can pay owners wages."),
        ("gpay", "Guaranteed payments", "0", "{pay}", "0", "0", "Partners get guaranteed payments (SE income)."),
        ("biz", "Business income/(loss) on 1040", "{ni}+{pay}", "{ni}*{pct}", "{ni}*{pct}", "0",
         "Sole prop adds back owner pay; C corp loss stays inside."),
        ("divs", "Dividend income", "0", "0", "0", "{dist}", "C corp distributions from E&P."),
        ("free", "Tax-free distribution", "0", "IF({basis_ok}=" + YES + ",{dist},0)",
         "IF({basis_ok}=" + YES + ",{dist},0)", "0", "Return of basis; excess is capital gain."),
        ("fica", "Subject to FICA", "0", "0", "{pay}", "{pay}", "Wages only."),
        ("set", "Subject to SE tax", "MAX(0,{ni}+{pay})", "IF({gp}=" + YES + ",{pay}+{ni}*{pct},{pay})", "0", "0",
         "LPs: guaranteed payments only."),
    ]
    for key, label, a, b, s, cc, why in rows:
        r = c.row
        c.put(f"B{r}", label, "text", "label")
        for col, f, suffix in (("C", a, "sp"), ("D", b, "pt"), ("E", s, "sc"), ("F", cc, "cc")):
            c.put(f"{col}{r}", f, "money", key=f"{key}_{suffix}")
        c.put(f"G{r}", why, "text", "label")
        c.row += 1
    c.gap()
    c.section("C CORPORATION TAXABLE INCOME (Form 1120)", "BCDEFG")
    c.inp("gi", "Gross income (excluding dividends received)", 500_000)
    c.inp("deds", "Deductions (expenses + depreciation; NOT dividends paid)", 350_000)
    c.inp("dr", "Dividends received from other corporations", 0)
    c.inp("own", "Ownership % of the paying corporation", 0.10, "pct")
    c.calc("r1", "DRD rate if < 20% owned", "IF({METHOD}=\"Law\",0.5,0.7)", "pct",
           note="Simplified: 70%. Law since 2018: 50%. Follows Method on Start.")
    c.calc("r2", "DRD rate if 20% to < 80% owned", "IF({METHOD}=\"Law\",0.65,0.8)", "pct",
           note="Simplified: 80%. Law: 65%.")
    c.inp("r3", "DRD rate if >= 80% owned", 1.00, "pct")
    c.inp("cc", "Charitable contributions", 0)
    c.inp("nolcf", "NOL carryforward (post-2017)", 0)
    c.calc("ti_pre", "Taxable income before special deductions", "{gi}+{dr}-{deds}")
    c.calc("ch", "Charitable deduction (10% of TI; 1% floor 2026+)",
           "MIN(MAX(0,{cc}-{P:corp_charity_floor}*MAX(0,{ti_pre})),{P:corp_charity_limit}*MAX(0,{ti_pre}))")
    c.calc("ti_ac", "TI after charity", "{ti_pre}-{ch}")
    c.calc("rate", "DRD %", "IF({own}>=0.8,{r3},IF({own}>=0.2,{r2},{r1}))", "pct")
    c.calc("drd_full", "DRD before TI limit", "{dr}*{rate}")
    c.calc("drd", "Dividends received deduction", "IF(AND({rate}<1,{ti_ac}-{drd_full}>0),MIN({drd_full},"
                                                  "{rate}*MAX(0,{ti_ac})),{drd_full})")
    c.calc("ti_pn", "TI before NOL", "{ti_ac}-{drd}")
    c.calc("nol", "NOL deduction (80% limit)", "MIN({nolcf},{P:nol_pct_limit}*MAX(0,{ti_pn}))")
    c.calc("cti", "TAXABLE INCOME", "{ti_pn}-{nol}", total=True)
    c.calc("ctax", "CORPORATE TAX (21%)", "ROUND(MAX(0,{cti})*{P:corp_rate},2)", total=True)
    c.gap()
    c.section("DOUBLE TAXATION", "BCDEFG")
    c.inp("dt_inc", "Pre-tax corporate income", 100_000)
    c.inp("dt_rate", "Shareholder rate on dividends", 0.238, "pct", note="20% + 3.8% NIIT, or 15% / 0%")
    c.calc("dt_corp", "Corporate tax", "{dt_inc}*{P:corp_rate}")
    c.calc("dt_div", "Dividend paid out", "{dt_inc}-{dt_corp}")
    c.calc("dt_sh", "Shareholder tax", "{dt_div}*{dt_rate}")
    c.calc("dt_total", "Combined tax", "{dt_corp}+{dt_sh}", total=True)
    c.calc("dt_eff", "Combined effective rate", "IF({dt_inc}<>0,{dt_total}/{dt_inc},0)", "pct", total=True)
    return c


# ==================================================================== BASIS ==
def build_basis(wb, reg):
    c = Calc(wb, reg, "Basis", "Partner / S Corp Shareholder Outside Basis Roll-Forward",
             "IRC 705, 1367. Order: +contributions, +income, -distributions, -losses.",
             widths=(2, 8, 14, 14, 14, 13, 12, 12, 13, 13, 12, 12, 12, 12, 13, 13))
    c.inp("pct", "Owner's share of income/loss", 0.30, "pct")
    c.inp("begin", "Beginning basis (year 1)", 0)
    c.gap()
    c.header_row(["Year", "Contributions", "Entity net income/(loss)", "Distributions to owner",
                  "Beginning basis", "Income share", "Loss share", "Basis before dist.", "Tax-free dist.",
                  "Gain (dist. > basis)", "Loss available", "Loss allowed", "Suspended loss c/f",
                  "Ending basis", "Net reported"], 2)
    data = [(200, 500, 400), (50, -1_000, 0), (250, 0, 0), (10_000, 833, 10_250)] + [(0, 0, 0)] * 4
    first = c.row
    for i, (ct, ni, d) in enumerate(data, start=1):
        r = c.row
        c.put(f"B{r}", i, "int", "label")
        c.put(f"C{r}", ct, "money", "input", key=f"c{i}")
        c.put(f"D{r}", ni, "money", "input", key=f"ni{i}")
        c.put(f"E{r}", d, "money", "input", key=f"d{i}")
        c.put(f"F{r}", "{begin}" if i == 1 else f"O{r - 1}", "money")
        c.put(f"G{r}", f"MAX(0,D{r}*{{pct}})", "money")
        c.put(f"H{r}", f"MAX(0,-D{r}*{{pct}})", "money")
        c.put(f"I{r}", f"F{r}+C{r}+G{r}", "money")
        c.put(f"J{r}", f"MIN(E{r},I{r})", "money", key=f"free{i}")
        c.put(f"K{r}", f"E{r}-J{r}", "money", key=f"gain{i}")
        c.put(f"L{r}", f"H{r}" if i == 1 else f"N{r - 1}+H{r}", "money")
        c.put(f"M{r}", f"MIN(L{r},I{r}-J{r})", "money", key=f"loss{i}")
        c.put(f"N{r}", f"L{r}-M{r}", "money", key=f"susp{i}")
        c.put(f"O{r}", f"I{r}-J{r}-M{r}", "money", "total", key=f"end{i}")
        c.put(f"P{r}", f"G{r}-M{r}+K{r}", "money", key=f"net{i}")
        c.row += 1
    del first
    c.gap()
    c.note("Pre-filled with an example (30% partner). Clear the blue cells for a new problem.")
    c.note("S corp: same mechanics for stock basis (debt basis not modeled). Partnership: add your share of "
           "liabilities to contributions if the problem asks for it.")
    return c


# ============================================================= DEPRECIATION ==
def build_depreciation(wb, reg):
    c = Calc(wb, reg, "Depreciation", "MACRS, Sec. 179, Bonus, Real Property, Amortization", "IRC 167, 168, 179, 195, 197.",
             widths=(2, 50, 18, 16, 16, 16, 40))
    last = int(reg.cells["MACRS_Tables"]["_last"]) if "MACRS_Tables" in reg.cells else 31
    c.section("PERSONAL PROPERTY (MACRS GDS)", "BCDEFG")
    c.inp("cost", "Cost", 25_000)
    c.inp("cls", "Recovery class (3, 5, 7, 10, 15, 20)", 7, "int", choices='"3,5,7,10,15,20"')
    c.inp("conv", "Convention (HY, Q1, Q2, Q3, Q4)", "HY", "text", choices='"HY,Q1,Q2,Q3,Q4"')
    c.inp("use", "Business-use %", 1.0, "pct")
    c.inp("s179", "Sec. 179 elected", 0)
    c.inp("bonus", "Bonus depreciation %", 0.0, "pct", note="100% for property acquired after 1/19/2025 (OBBBA)")
    c.calc("basis", "Depreciable basis (cost x business use)", "{cost}*{use}")
    c.calc("after179", "Basis after Sec. 179", "MAX(0,{basis}-{s179})")
    c.calc("bonus_amt", "Bonus depreciation", "{after179}*{bonus}")
    c.calc("mbasis", "MACRS basis", "{after179}-{bonus_amt}")
    c.calc("key", "(helper) table key", '{conv}&"|"&{cls}', "text")
    c.header_row(["Year", "MACRS %", "Depreciation", "Accumulated*", "Remaining basis"], 2)
    first = c.row
    for y in range(1, 22):
        r = c.row
        c.put(f"B{r}", y, "int", "label")
        c.put(f"C{r}", f"INDEX(MACRS_Tables!$D$2:$X${last},MATCH({{key}},MACRS_Tables!$A$2:$A${last},0),{y})",
              "0.000%", key=f"pct{y}")
        c.put(f"D{r}", f"{{mbasis}}*C{r}", "money", key=f"dep{y}")
        c.put(f"E{r}", f"{{s179}}+{{bonus_amt}}+SUM(D${first}:D{r})", "money")
        c.put(f"F{r}", f"{{basis}}-E{r}", "money")
        c.row += 1
    c.calc("yr1", "FIRST-YEAR TOTAL (179 + bonus + MACRS yr 1)", f"{{s179}}+{{bonus_amt}}+D{first}", total=True)
    c.note("*Accumulated includes Sec. 179 and bonus. In the year of sale take 1/2 year (HY) or the "
           "mid-quarter fraction (Q1 10.5/12 ... Q4 1.5/12) of that year's amount.")
    c.section("MID-QUARTER TEST", "BCDEFG")
    c.inp("q4", "Personal property placed in service in Q4", 41_000)
    c.inp("qtot", "Total personal property placed in service (excl. 179 & realty)", 100_000)
    c.calc("mq", "Convention required", 'IF({q4}>0.4*{qtot},IF({qtot}>0,"Mid-quarter","Half-year"),"Half-year")', "text",
           total=True)
    c.section("REAL PROPERTY (straight line, mid-month)", "BCDEFG")
    c.inp("rp_cost", "Building cost (exclude land)", 495_000)
    c.inp("rp_month", "Month placed in service (1-12)", 7, "int")
    c.inp("rp_res", "Residential rental (27.5 yr)? No = nonresidential 39 yr", "Yes", "text", choices="yesno")
    c.inp("rp_sold", "Month sold in a later year (0 if not sold)", 0, "int")
    c.calc("rp_months", "Recovery period (months)", "IF({rp_res}=" + YES + ",330,468)", "int")
    c.calc("rp_monthly", "Monthly depreciation", "{rp_cost}/{rp_months}")
    c.calc("rp_y1", "Year 1 depreciation", "{rp_monthly}*(12-{rp_month}+0.5)", total=True)
    c.calc("rp_full", "Full year depreciation", "{rp_monthly}*12", total=True)
    c.calc("rp_sale", "Year-of-sale depreciation", "IF({rp_sold}>0,{rp_monthly}*({rp_sold}-0.5),0)")
    c.section("SECTION 179 LIMIT", "BCDEFG")
    c.inp("s_total", "Total Sec. 179 property placed in service this year", 3_000_000)
    c.inp("s_elect", "Amount elected", 3_000_000)
    c.inp("s_cost", "Cost of the property", 3_000_000)
    c.inp("s_bti", "Business taxable income (limit)", 10_000_000)
    c.calc("s_lim", "Dollar limit after phase-out", "MAX(0,{P:sec179_limit}-MAX(0,{s_total}-{P:sec179_phaseout}))")
    c.calc("s_amt", "Sec. 179 before income limit", "MIN({s_elect},{s_cost},{s_lim})")
    c.calc("s_ded", "SEC. 179 DEDUCTION", "MIN({s_amt},MAX(0,{s_bti}))", total=True)
    c.calc("s_cf", "Carryforward (income limit)", "{s_amt}-{s_ded}")
    c.section("START-UP COSTS / SEC. 197 / MILEAGE", "BCDEFG")
    c.inp("su", "Start-up (or organizational) costs", 52_000)
    c.inp("su_m", "Months in first year", 12, "int")
    c.calc("su_imm", "Immediate deduction", "MAX(0,MIN({su},{P:startup_deduction}-MAX(0,{su}-{P:startup_phaseout})))")
    c.calc("su_y1", "FIRST-YEAR DEDUCTION (immediate + amortization)", "{su_imm}+({su}-{su_imm})/180*{su_m}", total=True)
    c.calc("su_ann", "Annual amortization thereafter", "({su}-{su_imm})/180*12")
    c.inp("i197", "Sec. 197 intangible cost (goodwill etc.)", 0)
    c.calc("a197", "Sec. 197 annual amortization (15 yrs)", "{i197}/15")
    c.inp("miles", "Business miles", 10_000, "num")
    c.calc("mile_d", "Standard mileage deduction", "{miles}*{P:mileage_business}", total=True)
    return c


# ============================================================ INCOME ITEMS ==
def build_income(wb, reg):
    c = Calc(wb, reg, "Income_Items", "Income Inclusions & Exclusions", "IRC 61, 74, 79, 86, 101-139, 911, 7872.",
             widths=(2, 52, 18, 50, 4, 10, 10))
    ws = c.ws
    ws["F4"], ws["G4"] = "GTL age", "$/1,000/mo"
    from ..params import GTL_TABLE
    for i, (age, rate) in enumerate(GTL_TABLE, start=5):
        ws[f"F{i}"], ws[f"G{i}"] = age, rate
    gtl_last = 4 + len(GTL_TABLE)
    c.section("SOCIAL SECURITY BENEFITS")
    c.inp("ss_status", "Filing status", "MFJ", "text", choices="status")
    c.inp("ss_ben", "Social Security benefits", 20_000)
    c.inp("ss_magi", "AGI excluding Social Security", 50_000)
    c.inp("ss_exempt", "Tax-exempt interest", 3_000)
    c.calc("b1", "Base amount 1", 'IF({ss_status}="MFJ",32000,IF({ss_status}="MFS",0,25000))', "money0")
    c.calc("b2", "Base amount 2", 'IF({ss_status}="MFJ",44000,IF({ss_status}="MFS",0,34000))', "money0")
    c.calc("pi", "Provisional income", "{ss_magi}+{ss_exempt}+0.5*{ss_ben}")
    c.calc("ss_tax", "TAXABLE SOCIAL SECURITY", "ROUND(IF({pi}<={b1},0,IF({pi}<={b2},MIN(0.5*({pi}-{b1}),0.5*{ss_ben}),"
                                                "MIN(0.85*({pi}-{b2})+MIN(0.5*{ss_ben},0.5*({b2}-{b1})),0.85*{ss_ben}))),2)",
           total=True)
    c.section("BELOW-MARKET LOAN (imputed interest)")
    c.inp("l_amt", "Loan amount", 67_500)
    c.inp("l_afr", "Applicable federal rate", 0.045, "pct")
    c.inp("l_rate", "Stated interest rate", 0.005, "pct")
    c.inp("l_type", "Loan type", "Gift", "text", choices='"Gift,Other"')
    c.inp("l_nii", "Borrower's net investment income", 2_750)
    c.inp("l_months", "Months outstanding in the year", 12, "int")
    c.calc("l_fore", "Foregone interest", "MAX(0,{l_amt}*({l_afr}-{l_rate})*{l_months}/12)")
    c.calc("l_imp", "IMPUTED INTEREST", "ROUND(IF({l_amt}>100000,{l_fore},IF({l_amt}<=10000,0,IF({l_type}=\"Gift\","
                                        "IF({l_nii}<=1000,0,MIN({l_fore},{l_nii})),{l_fore}))),2)", total=True)
    c.section("ANNUITY EXCLUSION RATIO")
    c.inp("a_inv", "Investment in the contract", 320_000)
    c.inp("a_pmt", "Monthly payment", 1_667)
    c.inp("a_mult", "Expected return multiple (Table V)", 20.0, "num", note="Age 65 = 20.0 (Reg. 1.72-9 Table V)")
    c.inp("a_years", "Years of payments already received", 5, "num")
    c.calc("a_annual", "Annual payments", "{a_pmt}*12")
    c.calc("a_er", "Expected return", "{a_annual}*{a_mult}")
    c.calc("a_ratio", "Exclusion ratio", "IF({a_er}>0,MIN(1,{a_inv}/{a_er}),0)", "pct")
    c.calc("a_ex0", "(helper) normal annual exclusion", "{a_annual}*{a_ratio}")
    c.calc("a_rec", "(helper) recovered so far", "{a_ex0}*{a_years}")
    c.calc("a_excl", "Excluded this year", "IF({a_rec}>={a_inv},0,IF({a_rec}+{a_ex0}>{a_inv},{a_inv}-{a_rec},{a_ex0}))")
    c.calc("a_tax", "TAXABLE THIS YEAR", "{a_annual}-{a_excl}", total=True)
    c.section("GROUP-TERM LIFE (over $50,000)")
    c.inp("g_cov", "Coverage", 250_000)
    c.inp("g_age", "Employee age at year end", 30, "int")
    c.inp("g_paid", "Amount paid by employee", 0)
    c.inp("g_months", "Months of coverage", 12, "int")
    c.calc("g_rate", "Table I cost per $1,000 / month", f"INDEX($G$5:$G${gtl_last},MATCH({{g_age}},$F$5:$F${gtl_last},1))",
           "$0.00")
    c.calc("g_inc", "TAXABLE GTL INCOME", "ROUND(MAX(0,MAX(0,{g_cov}-{P:gtl_exclusion})/1000*{g_rate}*{g_months}-{g_paid}),2)",
           total=True)
    c.section("FOREIGN EARNED INCOME EXCLUSION")
    c.inp("f_inc", "Foreign earned income in the year", 240_000)
    c.inp("f_days", "Qualifying days in the year", 239, "int")
    c.inp("f_ydays", "Days in the year", 365, "int")
    c.calc("f_excl", "EXCLUSION", "ROUND(MIN({f_inc},{P:feie_limit}*{f_days}/{f_ydays}),2)", total=True)
    c.section("LONG-TERM CARE BENEFITS")
    c.inp("ltc_cost", "Total LTC costs", 165_000)
    c.inp("ltc_days", "Days of care", 365, "int")
    c.inp("ltc_ins", "Insurance benefits received", 162_500)
    c.inp("ltc_med", "Medicare / other reimbursements", 37_500)
    c.calc("ltc_lim", "Excludable amount", "MAX({P:ltc_per_diem}*{ltc_days},{ltc_cost})-{ltc_med}")
    c.calc("ltc_tax", "TAXABLE LTC BENEFITS", "ROUND(MAX(0,{ltc_ins}-{ltc_lim}),2)", total=True)
    c.section("SCHOLARSHIP / DAMAGES / STATE REFUND")
    c.inp("sch_tot", "Scholarship received", 75_000)
    c.inp("sch_tuit", "Qualified tuition, fees, books", 55_000)
    c.calc("sch_tax", "Taxable scholarship (room & board)", "MAX(0,{sch_tot}-{sch_tuit})", total=True)
    c.inp("dm_award", "Property damage award", 50_000)
    c.inp("dm_basis", "Basis of damaged property", 2_000)
    c.calc("dm_tax", "Taxable damages", "MAX(0,{dm_award}-{dm_basis})", total=True)
    c.inp("tb_ref", "State refund received", 1_500)
    c.inp("tb_item", "Prior-year itemized deductions claimed (0 if standard)", 32_000)
    c.inp("tb_std", "Prior-year standard deduction", 31_500)
    c.calc("tb_inc", "Refund included in income (tax benefit rule)",
           "IF({tb_item}<=0,0,MIN({tb_ref},MAX(0,{tb_item}-{tb_std})))", total=True)
    c.section("OID / ACCRUED INTEREST (compounded CD)")
    c.inp("o_prin", "Principal", 10_000)
    c.inp("o_rate", "Annual rate", 0.05, "pct")
    c.header_row(["Year", "Interest to report", "Ending balance"], 2)
    for y in range(1, 6):
        r = c.row
        c.put(f"B{r}", y, "int", "label")
        prev = "{o_prin}" if y == 1 else f"D{r - 1}"
        c.put(f"C{r}", f"ROUND({prev}*{{o_rate}},2)", "money", key=f"oid{y}")
        c.put(f"D{r}", f"{prev}+C{r}", "money")
        c.row += 1
    return c


# ==================================================================== LOSSES ==
def build_losses(wb, reg):
    c = Calc(wb, reg, "Losses", "Casualty, Excess Business Loss, NOL, Vacation Home, Hobby", "IRC 165, 172, 183, 280A, 461(l).")
    c.section("CASUALTY LOSS")
    c.inp("cl_basis", "Adjusted basis", 100_000)
    c.inp("cl_before", "FMV before", 110_000)
    c.inp("cl_after", "FMV after", 20_000)
    c.inp("cl_ins", "Insurance recovery", 60_000)
    c.inp("cl_agi", "AGI", 120_000)
    c.inp("cl_pers", "Personal-use property?", "Yes", "text", choices="yesno",
          note="Personal: only federally (2026+: or qualifying state) declared disasters")
    c.inp("cl_dest", "Business property completely destroyed?", "No", "text", choices="yesno")
    c.inp("cl_qd", "Qualified disaster ($500, no 10% floor)?", "No", "text", choices="yesno")
    c.calc("cl_base", "Loss measure", "IF(AND({cl_pers}=\"No\",{cl_dest}=" + YES + "),{cl_basis},"
                                    "MIN({cl_basis},{cl_before}-{cl_after}))")
    c.calc("cl_loss", "Loss after insurance", "MAX(0,{cl_base}-{cl_ins})")
    c.calc("cl_event", "Less: per-event amount", "IF({cl_pers}=" + YES + ",IF({cl_qd}=" + YES + ",500,{P:casualty_per_event}),0)")
    c.calc("cl_floor", "Less: 10% of AGI", "IF(AND({cl_pers}=" + YES + ",{cl_qd}=\"No\"),{P:casualty_agi_pct}*{cl_agi},0)")
    c.calc("cl_ded", "DEDUCTIBLE CASUALTY LOSS", "ROUND(MAX(0,MAX(0,{cl_loss}-{cl_event})-{cl_floor}),2)", total=True)
    c.section("EXCESS BUSINESS LOSS (Sec. 461(l))")
    c.inp("eb_status", "Filing status", "HOH", "text", choices="status")
    c.inp("eb_inc", "Business gross income", 320_000)
    c.inp("eb_ded", "Business deductions", 700_000)
    c.calc("eb_loss", "Net business loss", "MAX(0,{eb_ded}-{eb_inc})")
    c.calc("eb_thr", "Threshold", "{PS:ebl_threshold:eb_status}")
    c.calc("eb_allow", "LOSS ALLOWED THIS YEAR", "MIN({eb_loss},{eb_thr})", total=True)
    c.calc("eb_nol", "Excess -> NOL carryforward", "{eb_loss}-{eb_allow}", total=True)
    c.section("NOL - COMPUTE (simplified)")
    c.inp("n_ti", "Taxable income (negative)", -45_000)
    c.inp("n_cg", "Net capital gain included", 11_000)
    c.inp("n_std", "Standard / itemized deduction claimed", 30_000)
    c.inp("n_nbi", "Non-business income", 8_000)
    c.calc("n_nol", "NOL CARRYFORWARD", "MAX(0,-({n_ti}-{n_cg}+{n_std}-{n_nbi}))", total=True)
    c.section("NOL - APPLY (80% limit)")
    c.inp("na_ti", "Taxable income before NOL", 48_400)
    c.inp("na_cf", "NOL carryforward available", 34_000)
    c.calc("na_ded", "NOL DEDUCTION", "ROUND(MIN({na_cf},{P:nol_pct_limit}*MAX(0,{na_ti})),2)", total=True)
    c.calc("na_ti2", "Taxable income after NOL", "{na_ti}-{na_ded}")
    c.calc("na_left", "NOL remaining", "{na_cf}-{na_ded}")
    c.section("VACATION HOME / DUAL-USE PROPERTY (Sec. 280A)")
    c.inp("v_rent_d", "Days rented at fair rent", 80, "int")
    c.inp("v_pers_d", "Personal-use days", 20, "int")
    c.inp("v_rent", "Gross rental income", 24_000)
    c.inp("v_int", "Mortgage interest", 18_250)
    c.inp("v_tax", "Property taxes", 7_300)
    c.inp("v_op", "Operating (utilities, insurance, repairs)", 9_600)
    c.inp("v_dep", "Depreciation (full year)", 10_000)
    c.inp("v_direct", "Direct rental expenses (advertising, fees)", 850)
    c.inp("v_method", "Interest/tax allocation method", "Tax Court", "text", choices='"Tax Court,IRS"',
          note="Tax Court (Bolton): rental days / 365. IRS: rental / total use days.")
    c.calc("v_it", "(helper) interest + taxes", "{v_int}+{v_tax}")
    c.calc("v_oppct", "Rental % (rental / total use days)", "IF({v_rent_d}+{v_pers_d}>0,{v_rent_d}/({v_rent_d}+{v_pers_d}),0)",
           "pct")
    c.calc("v_lim", "Personal-use limit: greater of 14 or 10% of rental days", "MAX(14,0.1*{v_rent_d})", "num")
    c.calc("v_code", "(helper) 0 minimal, 1 rental, 2 dual use", "IF({v_rent_d}<15,0,IF({v_pers_d}<={v_lim},1,2))", "int")
    c.calc("v_class", "CLASSIFICATION", 'IF({v_code}=0,"Minimal rental - rent excluded",IF({v_code}=1,'
                                       '"Primarily rental - loss allowed","Dual use - expenses limited to rent"))',
           "text", total=True)
    c.calc("v_itpct", "Interest/tax rental %", "IF({v_code}=2,IF({v_method}=\"Tax Court\",{v_rent_d}/365,{v_oppct}),"
                                               "{v_oppct})", "pct")
    c.calc("v_rem0", "(helper) rent less direct", "{v_rent}-{v_direct}")
    c.calc("v_it_r", "Interest & taxes on Schedule E", "ROUND(IF({v_code}=0,0,IF({v_code}=1,{v_it}*{v_oppct},"
                                                      "MIN({v_it}*{v_itpct},MAX(0,{v_rem0})))),2)")
    c.calc("v_op_r", "Operating expenses on Schedule E", "ROUND(IF({v_code}=0,0,IF({v_code}=1,{v_op}*{v_oppct},"
                                                        "MIN({v_op}*{v_oppct},MAX(0,{v_rem0}-{v_it_r})))),2)")
    c.calc("v_dep_r", "Depreciation on Schedule E", "ROUND(IF({v_code}=0,0,IF({v_code}=1,{v_dep}*{v_oppct},"
                                                   "MIN({v_dep}*{v_oppct},MAX(0,{v_rem0}-{v_it_r}-{v_op_r})))),2)")
    c.calc("v_net", "NET RENTAL INCOME/(LOSS)", "IF({v_code}=0,0,{v_rem0}-{v_it_r}-{v_op_r}-{v_dep_r})", total=True)
    c.calc("v_scha", "Interest & taxes left for Schedule A", "{v_it}-{v_it_r}")
    c.section("HOBBY")
    c.inp("h_rec", "Gross receipts", 8_000)
    c.inp("h_cogs", "Cost of goods sold", 2_000)
    c.calc("h_inc", "Hobby income reported (expenses not deductible)", "{h_rec}-{h_cogs}", total=True)
    c.inp("h_years", "Profitable years in last 5", 2, "int")
    c.calc("h_pres", "Presumed for-profit (3 of 5)?", 'IF({h_years}>=3,"Yes","No")', "text")
    return c


# ================================================================ RETIREMENT ==
def build_retirement(wb, reg):
    c = Calc(wb, reg, "Retirement", "IRA, Roth & Self-Employed Retirement", "IRC 219, 404, 408, 408A.")

    def phase(full, magi, start, rng):
        return (f"IF({magi}<={start},{full},IF({magi}>={start}+{rng},0,MIN({full},MAX(200,"
                f"CEILING({full}*({start}+{rng}-{magi})/{rng},10)))))")

    c.section("TRADITIONAL IRA DEDUCTION")
    c.inp("status", "Filing status", "S", "text", choices="status")
    c.inp("contrib", "Contribution", 7_500)
    c.inp("comp", "Compensation", 100_000)
    c.inp("age", "Age", 35, "int")
    c.inp("magi", "Modified AGI", 90_740)
    c.inp("covered", "Covered by a workplace plan?", "Yes", "text", choices="yesno")
    c.inp("sp_cov", "Spouse covered (MFJ only)?", "No", "text", choices="yesno")
    c.calc("full", "Contribution limit", "{P:ira_limit}+IF({age}>=50,{P:ira_catchup},0)")
    c.calc("limit", "Limit (capped at compensation)", "MIN({full},MAX(0,{comp}))")
    c.calc("c_ok", "Allowed contribution", "MIN({contrib},{limit})")
    c.calc("mode", "(helper) 1 covered, 2 spouse-only, 0 none",
           "IF({covered}=" + YES + ",1,IF(AND({sp_cov}=" + YES + ",{status}=\"MFJ\"),2,0))", "int")
    c.calc("pstart", "Phase-out start", "IF({mode}=1,{PS:ira_phase_start_covered:status},{P:ira_phase_start_spouse})")
    c.calc("prange", "Phase-out range", "IF({mode}=1,{PS:ira_phase_range_covered:status},10000)")
    c.calc("pallowed", "Deduction limit after phase-out ($10 round-up, $200 min)",
           phase("{full}", "{magi}", "{pstart}", "{prange}"))
    c.calc("ira_ded", "DEDUCTIBLE IRA CONTRIBUTION", "IF({mode}=0,{c_ok},MIN({c_ok},{pallowed}))", total=True)
    c.calc("nondeduct", "Nondeductible portion (basis)", "{c_ok}-{ira_ded}")
    c.section("ROTH IRA CONTRIBUTION LIMIT")
    c.calc("roth", "MAX ROTH CONTRIBUTION", phase("{limit}", "{magi}", "{PS:roth_phase_start:status}",
                                                  "{PS:roth_phase_range:status}"), total=True)
    c.section("SEP-IRA (self-employed)")
    c.inp("sep_inc", "Net self-employment income", 100_000)
    c.inp("sep_half", "Deductible 1/2 SE tax", 7_064.78)
    c.calc("sep_short", "Use simplified shortcut (20% of SE income)?", 'IF({METHOD}="Law","No","Yes")', "text",
           note="Follows Method on Start. Law: 20% x (net SE income - 1/2 SE tax)")
    c.calc("sep", "SEP DEDUCTION", "ROUND(MIN({P:sep_pct_se}*MAX(0,IF({sep_short}=" + YES + ",{sep_inc},"
                                   "{sep_inc}-{sep_half})),{P:dc_limit}),2)", total=True)
    c.section("401(k) LIMIT")
    c.inp("k_age", "Age", 61, "int")
    c.calc("k_lim", "Elective deferral limit incl. catch-up", "{P:k401_limit}+IF(AND({k_age}>=60,{k_age}<=63),"
                                                             "{P:k401_catchup_60_63},IF({k_age}>=50,{P:k401_catchup},0))",
           total=True)
    return c


BUILDERS = [build_1040, build_sch_a, build_payroll, build_std_credits, build_capital, build_entities,
            build_basis, build_depreciation, build_income, build_losses, build_retirement]

INDEX = [
    ("Form_1040", "IRC 1, 62, 63", "Complete return: income, AGI, standard vs itemized, Sch. 1-A, QBI, tax, "
                                    "SE tax, NIIT, CTC, refund."),
    ("Sch_A", "IRC 163-213", "Medical, SALT cap phase-down, mortgage limit, investment interest, charity limits & "
                         "0.5% floor, gambling."),
    ("Payroll_SE", "IRC 1401, 1411", "Employer/employee FICA, 0.9% Medicare, SE tax and deduction, NIIT."),
    ("Std_Ded_Credits", "IRC 24, 63", "Standard deduction (incl. dependents), kiddie tax, CTC/ODC/ACTC, "
                                      "senior/tips/overtime/car-loan deductions."),
    ("Capital", "IRC 1001, 1211", "Amount realized, adjusted basis, Sec. 121, capital loss netting & carryforward, "
                                "stock splits, foreclosure."),
    ("Entities", "IRC 11, 243", "What the owner reports under each entity, C corp TI with DRD, double taxation."),
    ("Basis", "IRC 705, 1367", "Multi-year partner / S corp basis with suspended losses."),
    ("Depreciation", "IRC 168, 179", "MACRS schedule with 179 & bonus, mid-quarter test, real property, startup "
                                   "costs, mileage."),
    ("Income_Items", "IRC 61-139", "Social Security, imputed interest, annuities, GTL, FEIE, LTC, scholarships, "
                                  "tax benefit rule, OID."),
    ("Losses", "IRC 165, 172", "Casualty loss, excess business loss, NOL, vacation home (both methods), hobby."),
    ("Retirement", "IRC 219, 408", "IRA deduction phase-out, Roth limit, SEP, 401(k) limits."),
]
