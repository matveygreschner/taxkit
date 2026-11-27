"""Worked examples (textbook-style problems) checked against the engine.

Each test asserts the correct computed value.
"""
import pytest

from taxkit import depreciation as dep
from taxkit import entities as ent
from taxkit import income as inc
from taxkit import individual as ind
from taxkit import itemized as itm
from taxkit import losses as los
from taxkit import payroll as pay
from taxkit import property as prop
from taxkit import retirement as ret
from taxkit.rates import income_tax, ordinary_tax, per_band_min_tax

Y = 2026


class TestEntities:
    def test_owner_single_member_llc(self):
        r = ent.owner_reporting("sole_prop", -55_000, 100_000)
        assert r.business_income == 45_000 and r.subject_to_se_tax == 45_000

    def test_owner_c_corp(self):
        r = ent.owner_reporting("c_corp", -55_000, 100_000, distributions=40_000)
        assert (r.wages_w2, r.dividends, r.subject_to_fica) == (100_000, 40_000, 100_000)

    def test_owner_s_corp(self):
        r = ent.owner_reporting("s_corp", -55_000, 100_000, distributions=40_000)
        assert (r.wages_w2, r.business_income, r.tax_free_distribution) == (100_000, -55_000, 40_000)
        assert r.subject_to_se_tax == 0

    def test_owner_partnership(self):
        r = ent.owner_reporting("partnership", -55_000, 100_000, distributions=40_000, ownership_pct=0.5)
        assert r.guaranteed_payments == 100_000
        assert r.business_income == -27_500
        assert r.subject_to_se_tax == 72_500

    def test_jake_peralta_fica(self):
        # MFJ, wages $275,000
        r = pay.fica(275_000, "MFJ", Y)
        assert r.employer_total == pytest.approx(11_439 + 3_987.50)
        assert r.additional_medicare == pytest.approx(225.00)

    def test_terry_jeffords_fica(self):
        r = pay.fica(375_000, "MFJ", Y)
        assert r.employer_total == pytest.approx(11_439 + 5_437.50)
        assert r.additional_medicare == pytest.approx(1_125.00)

    def test_ray_holt_se_tax(self):
        r = pay.self_employment_tax(275_000, "MFJ", Y)
        assert r.net_earnings == pytest.approx(253_962.50)
        assert r.se_tax == pytest.approx(22_878 + 7_364.91, abs=0.01)
        assert r.deduction_half == pytest.approx(15_121.46, abs=0.01)
        assert r.additional_medicare == pytest.approx(35.66, abs=0.01)

    def test_drd_simplified_vs_law(self):
        simp = ent.c_corp_tax(400_000, 100_000, 100_000, 0.10, method="simplified")
        law = ent.c_corp_tax(400_000, 100_000, 100_000, 0.10, method="law")
        assert simp.drd == 70_000 and law.drd == 50_000

    def test_c_corp_taxable_income(self):
        # GI 500K, expenses 150K, depreciation 200K, dividends PAID 110K (not deductible)
        r = ent.c_corp_tax(500_000, 150_000 + 200_000)
        assert r.taxable_income == 150_000 and r.tax == 31_500

    def test_gamma_partnership_basis(self):
        rows = ent.basis_rollforward(
            contributions=[200, 50, 250, 10_000], net_income=[500, -1_000, 0, 833],
            distributions=[400, 0, 0, 10_250], ownership_pct=0.30)
        y1, y2, y3, y4 = rows
        assert (y1.ending_basis, y1.income_share, y1.tax_free_distribution, y1.taxable_distribution_gain) == (
            0, 150, 350, 50)
        assert (y2.ending_basis, y2.loss_allowed, y2.loss_suspended_cf) == (0, 50, 250)
        assert (y3.ending_basis, y3.loss_allowed) == (0, 250)
        assert y4.income_share == pytest.approx(249.9)
        assert y4.ending_basis == pytest.approx(0, abs=0.01)


class TestCapitalTransactions:
    def test_estate_sale(self):
        ar = prop.amount_realized(1_500_000, 2_500_000, 500_000, 45_000)
        ab = prop.adjusted_basis(200_000, 200_000, 55_000)   # $30K repairs are not capitalized
        assert ar == 4_455_000 and ab == 345_000
        assert prop.sale(ar, ab).realized == 4_110_000

    @pytest.mark.parametrize("price, net_lt, deductible, st_cf", [
        (210, 11_000, 0, 0),
        (199, 0, 1_100, 0),
        (190, 0, 3_000, 8_000),
    ])
    def test_rafael_stock_dividend(self, price, net_lt, deductible, st_cf):
        lot = prop.stock_after_split_or_stock_dividend(prop.StockLot(1_000, 100_000), 1.10)
        gain = lot.shares * price - lot.total_basis
        r = prop.net_capital_gains(lt_gains=gain, st_losses=120_000, year=2025)
        assert r.taxable_lt_gain == pytest.approx(net_lt)
        assert r.deductible_loss == pytest.approx(deductible)
        assert r.st_carryforward == pytest.approx(st_cf)


class TestTaxBasics:
    @pytest.mark.parametrize("status, expected", [
        ("MFJ", 81_196.00),
        ("HOH", 106_961.00),
        ("S", 108_769.25),
        ("MFS", 109_082.25),
    ])
    def test_400k_by_status(self, status, expected):
        assert ordinary_tax(400_000, status, Y) == pytest.approx(expected)

    def test_400k_all_ltcg_simplified_method(self):
        # Simplified method ("pick smaller" per band).
        assert income_tax(400_000, "S", Y, net_ltcg=400_000, method="simplified").tax == pytest.approx(52_554.00)
        assert per_band_min_tax(400_000, 400_000, "S", Y) == pytest.approx(52_554.00)

    def test_400k_all_ltcg_law(self):
        r = income_tax(400_000, "S", Y, net_ltcg=400_000, method="law")
        assert r.tax == pytest.approx(52_582.50)            # statutory Schedule D worksheet
        assert r.ancg_at_0 == 49_450

    def test_methods_agree_when_no_low_band_overlap(self):
        # MFJ, gains entirely above the 22% bracket: both methods give the same answer.
        a = income_tax(300_000, "MFJ", Y, net_ltcg=50_000, method="simplified").tax
        b = income_tax(300_000, "MFJ", Y, net_ltcg=50_000, method="law").tax
        assert a == pytest.approx(b)

    def test_standard_deductions(self):
        assert ind.standard_deduction("S", 2025) == 15_750
        assert ind.standard_deduction("MFJ", 2025) == 31_500
        assert ind.standard_deduction("HOH", 2025) == 23_625
        assert ind.standard_deduction("S", Y) == 16_100
        assert ind.standard_deduction("S", 2025, age65_or_blind_boxes=1) == 17_750
        assert ind.standard_deduction("MFJ", 2025, age65_or_blind_boxes=2) == 34_700

    def test_xochi_dependent_std_deduction(self):
        assert ind.standard_deduction("S", Y, is_dependent=True, earned_income=7_600) == 8_050

    @pytest.mark.parametrize("earned, expected", [
        (0, 1_350), (5_000, 5_450), (25_000, 16_100),
    ])
    def test_dependent_std_examples(self, earned, expected):
        # mixed $5K earned / $5K unearned: $5,450
        assert ind.standard_deduction("S", Y, is_dependent=True, earned_income=earned) == expected

    def test_senior_deduction_phaseout(self):
        assert ind.senior_deduction(1, 75_000, "S", 2025) == 6_000
        assert ind.senior_deduction(1, 175_000, "S", 2025) == 0
        assert ind.senior_deduction(1, 125_000, "S", 2025) == 3_000
        assert ind.senior_deduction(2, 150_000, "MFJ", 2025) == 12_000
        assert ind.senior_deduction(1, 100_000, "MFS", 2025) == 0

    def test_child_tax_credit_phaseout(self):
        r = ind.child_tax_credit(1, 0, 450_000, "MFJ", 50_000, 450_000, Y)
        assert r.after_phaseout == 0     # $2,200 - 50 x $50 = $0 at $450K
        r = ind.child_tax_credit(2, 1, 100_000, "MFJ", 10_000, 100_000, Y)
        assert r.after_phaseout == 4_900 and r.nonrefundable_used == 4_900

    def test_actc_refundable(self):
        r = ind.child_tax_credit(2, 0, 30_000, "HOH", 500, 30_000, Y)
        assert r.nonrefundable_used == 500
        assert r.refundable_actc == 3_400

    def test_kiddie_tax_unearned_only(self):
        r = ind.kiddie_tax(0, 10_000, 200_000, "MFJ", Y)
        assert r.child_std_deduction == 1_350
        assert r.net_unearned_income == 7_300
        assert r.tax_at_parent_rate == pytest.approx(7_300 * 0.22)


class TestIncome:
    def test_grace_abbie_imputed_interest(self):
        assert inc.imputed_interest(67_500, 0.045, 0.005, "gift", borrower_nii=2_750) == 2_700

    def test_imputed_over_100k(self):
        assert inc.imputed_interest(200_000, 0.10, 0.0) == 20_000

    def test_imputed_small_loan(self):
        assert inc.imputed_interest(9_000, 0.10, 0.0) == 0

    def test_emma_annuity(self):
        at70 = inc.annuity_exclusion(320_000, 1_667, 20.0, years_received_so_far=5)
        assert at70.annual_excluded == pytest.approx(16_000, abs=1)
        assert at70.annual_taxable == pytest.approx(4_004, abs=1)
        at95 = inc.annuity_exclusion(320_000, 1_667, 20.0, years_received_so_far=30)
        assert at95.annual_taxable == pytest.approx(20_004)

    def test_john_mary_social_security(self):
        r = ind.taxable_social_security(20_000, 30_000 + 5_000 + 15_000, 3_000, "MFJ")
        assert r.provisional_income == 63_000 and r.taxable_benefits == 17_000

    def test_capital_netting(self):
        a = prop.net_capital_gains(lt_gains=15_000, st_losses=10_000)
        assert a.taxable_lt_gain == 5_000 and a.taxable_st_gain == 0
        b = prop.net_capital_gains(lt_gains=15_000, st_losses=100_000)
        assert b.deductible_loss == 3_000 and b.st_carryforward == 82_000

    def test_home_sale(self):
        assert prop.home_sale_exclusion("MFJ", Y) == 500_000
        assert prop.home_sale_exclusion("S", Y, 12, 12, partial_reason=True) == 125_000
        assert prop.sale(1_000_000, 200_000, sec121_exclusion=500_000).recognized == 300_000

    def test_oid_cd(self):
        rows = inc.oid_accrual(10_000, 0.05, 4)
        assert [r[1] for r in rows] == [500.0, 525.0, 551.25, 578.81]


class TestExclusions:
    def test_group_term_life(self):
        assert inc.group_term_life_income(250_000, 30) == 192

    def test_feie(self):
        assert inc.feie(240_000, 239, 2025) == pytest.approx(85_123.29, abs=0.01)
        assert inc.feie(60_000, 71, 2026) == pytest.approx(25_851.78, abs=0.01)

    def test_long_term_care(self):
        assert inc.ltc_taxable(165_000, 365, 162_500, 37_500, 2025) == 35_000

    def test_scholarship(self):
        assert inc.scholarship_taxable(75_000, 55_000) == 20_000

    def test_car_damages(self):
        assert inc.property_damages_taxable(50_000, 2_000) == 48_000

    def test_foreclosure(self):
        rec = prop.foreclosure(60_000, 10_000, 25_000, recourse=True)
        assert (rec.gain_on_disposition, rec.cancellation_of_debt_income) == (15_000, 35_000)
        nr = prop.foreclosure(60_000, 10_000, 25_000, recourse=False)
        assert (nr.gain_on_disposition, nr.cancellation_of_debt_income) == (50_000, 0)


class TestDeductions:
    def test_james_14_day_rule(self):
        r = los.vacation_home(14, 30, 80_000, 0, 0, 0, 0)
        assert r.classification.startswith("minimal")

    def test_james_90_days_10_personal(self):
        r = los.vacation_home(90, 10, 50_000, 0, 0, 10_000, 0)
        assert r.classification == "primarily rental"
        assert r.rental_pct_for_operating == pytest.approx(0.9)

    def test_sarah_dual_use_tax_court(self):
        r = los.vacation_home(80, 20, 24_000, 18_250, 7_300, 4_000 + 2_400 + 3_200, 10_000,
                              direct_rental_expenses=850, method="tax_court")
        assert r.classification.startswith("dual use")
        assert r.interest_taxes_rental == pytest.approx(5_600)
        assert r.operating_rental == pytest.approx(7_680)
        assert r.depreciation_rental == pytest.approx(8_000)
        assert r.net_rental_income == pytest.approx(1_870)
        assert r.interest_taxes_to_schedule_a == pytest.approx(19_950)

    def test_sarah_dual_use_irs(self):
        r = los.vacation_home(80, 20, 24_000, 18_250, 7_300, 9_600, 10_000,
                              direct_rental_expenses=850, method="irs")
        assert r.interest_taxes_rental == pytest.approx(20_440)
        assert r.operating_rental == pytest.approx(2_710)
        assert r.net_rental_income == pytest.approx(0)


class TestLosses:
    def test_gwagon_business(self):
        r = los.casualty_loss(100_000, 110_000, 20_000, 60_000, 120_000, personal=False,
                              completely_destroyed_business=True)
        assert r.deductible == 40_000

    @pytest.mark.parametrize("agi, expected", [(100_000, 19_900), (120_000, 17_900)])
    def test_gwagon_personal(self, agi, expected):
        r = los.casualty_loss(100_000, 110_000, 20_000, 60_000, agi, personal=True)
        assert r.loss_before_limits == 30_000 and r.deductible == expected

    def test_excess_business_loss(self):
        hoh = los.excess_business_loss(320_000, 700_000, "HOH", Y)
        assert (hoh.net_business_loss, hoh.allowed, hoh.disallowed_to_nol) == (380_000, 256_000, 124_000)
        mfj = los.excess_business_loss(320_000, 700_000, "MFJ", Y)
        assert mfj.disallowed_to_nol == 0

    def test_nol_computation(self):
        assert los.compute_nol(-45_000, 11_000, 30_000, 8_000) == 34_000

    def test_nol_80_pct(self):
        r = los.apply_nol(10_000, 34_000)
        assert r.nol_deduction == 8_000 and r.nol_carryforward_remaining == 26_000


class TestDepreciation:
    def test_residential_rental_july(self):
        rows = dep.real_property_depreciation(495_000, 7, residential=True)
        assert rows[0].depreciation == 8_250 and rows[1].depreciation == 18_000

    def test_commercial_july(self):
        rows = dep.real_property_depreciation(1_404_000, 7, residential=False)
        assert rows[0].depreciation == 16_500 and rows[1].depreciation == 36_000

    def test_computer_5_year(self):
        s = dep.personal_property_schedule(25_000, 5, "HY")
        assert [r.depreciation for r in s.schedule] == [5_000, 8_000, 4_800, 2_880, 2_880, 1_440]

    def test_couch_7_year(self):
        s = dep.personal_property_schedule(25_000, 7, "HY")
        assert [r.depreciation for r in s.schedule[:3]] == [3_572.50, 6_122.50, 4_372.50]

    def test_mid_quarter_trigger(self):
        assert dep.needs_mid_quarter(41_000, 100_000) and not dep.needs_mid_quarter(40_000, 100_000)

    def test_sec179_and_bonus(self):
        s = dep.personal_property_schedule(100_000, 7, "HY", sec179=30_000, bonus_pct=0.4)
        assert s.bonus == 28_000 and s.macrs_basis == 42_000
        assert s.first_year_total == pytest.approx(30_000 + 28_000 + 42_000 * 0.1429)

    def test_sec179_phaseout(self):
        ded, cf = dep.sec179_allowed(3_000_000, 5_000_000, 3_000_000, year=2025)
        assert ded == 1_500_000 and cf == 0

    def test_startup_costs(self):
        assert dep.startup_costs(52_000, 12)[0] == pytest.approx(3_000 + 49_000 / 15)
        assert dep.startup_costs(60_000, 12)[0] == pytest.approx(4_000)


class TestBusiness:
    def test_se_example(self):
        se = pay.self_employment_tax(100_000, "S", Y)
        assert se.se_tax == pytest.approx(14_129.55)
        assert 100_000 - se.deduction_half == pytest.approx(92_935.22, abs=0.01)

    def test_owner_ira_minimum_200(self):
        assert ret.traditional_ira_deduction(7_500, 90_740, "S", covered_by_plan=True) == 200

    def test_ira_partial(self):
        assert ret.traditional_ira_deduction(7_500, 85_000, "S", covered_by_plan=True) == 4_500

    def test_ira_not_covered(self):
        assert ret.traditional_ira_deduction(7_500, 500_000, "S", covered_by_plan=False) == 7_500

    def test_tips_and_overtime(self):
        assert ind.tips_deduction(30_000, 100_000, "S", Y) == 25_000
        assert ind.tips_deduction(30_000, 200_000, "S", Y) == 20_000
        assert ind.overtime_deduction(20_000, 100_000, "MFJ", Y) == 20_000
        assert ind.overtime_deduction(20_000, 100_000, "S", Y) == 12_500

    def test_sep(self):
        assert ret.sep_deduction(100_000) == 20_000                                  # simplified shortcut
        assert ret.sep_deduction(100_000, 7_064.78, method="law") == pytest.approx(18_587.04)
        assert ret.sep_deduction(1_000_000) == 72_000


class TestItemized:
    def test_salt_cap_phase_down(self):
        assert itm.salt_cap(300_000, "MFJ", Y) == 40_400
        assert itm.salt_cap(555_000, "MFJ", Y) == pytest.approx(25_400)
        assert itm.salt_cap(1_000_000, "MFJ", Y) == 10_000
        assert itm.salt_cap(100_000, "MFS", Y) == 20_200

    def test_charity_floor_2026(self):
        r = itm.charitable_deduction(200_000, cash_public=5_000, year=2026)
        assert r.floor == 1_000 and r.deduction == 4_000

    def test_donated_stock(self):
        # ST Amazon -> basis $7,500 ; LT Apple -> FMV $10,000
        r = itm.charitable_deduction(1_000_000, property_ltcg_public=10_000, cash_public=7_500, year=2025)
        assert r.deduction == 17_500

    def test_mortgage_proration(self):
        assert itm.mortgage_interest_deduction(60_000, 1_000_000, "MFJ", Y) == 45_000

    def test_gambling_90pct(self):
        assert itm.gambling_loss_deduction(100_000, 100_000, 2026) == 90_000
        assert itm.gambling_loss_deduction(100_000, 100_000, 2025) == 100_000

    def test_medical_floor(self):
        assert itm.medical_deduction(10_000, 100_000) == 2_500


class TestCodexRegressionsIndividual:
    """Individual-engine cases from the independent Codex review (each was a confirmed bug)."""

    def test_schedule_d_25pct_gain_stacks_above_ancg(self):
        # IRC 1(h): ANCG sits right above amount (A); the 25% gain is taxed at 25% on top.
        assert income_tax(600_000, "S", 2025, net_ltcg=400_000, unrecaptured_1250=350_000).tax == 136_063

    def test_joint_se_uses_own_wage_base(self):
        from taxkit.form1040 import Return1040, compute_return
        r = compute_return(Return1040(year=2025, status="MFJ", wages=176_100, schedule_c_profit=100_000))
        assert r.se_tax == pytest.approx(14_129.55) and r.additional_medicare == pytest.approx(166.05)

    def test_qss_additional_medicare_threshold(self):
        from taxkit.form1040 import Return1040, compute_return
        assert compute_return(Return1040(year=2025, status="QSS", wages=225_000)).additional_medicare == 225
        assert pay.niit(100_000, 260_000, "QSS", 2025) == pytest.approx(380)

    def test_qbi_nets_schedule_c_loss(self):
        from taxkit.form1040 import Return1040, compute_return
        r = compute_return(Return1040(year=2025, wages=100_000, schedule_c_profit=-30_000, other_qbi=50_000))
        assert r.qbi_deduction == 4_000

    def test_qbi_minimum_on_return(self):
        from taxkit.form1040 import Return1040, compute_return
        r = compute_return(Return1040(year=2026, wages=14_600, other_income=2_000, other_qbi=2_000))
        assert r.qbi_deduction == 400

    def test_salt_mfs_phase_down(self):
        assert itm.salt_cap(275_000, "MFS", 2025) == 16_250

    def test_senior_deduction_per_person(self):
        assert ind.senior_deduction(2, 200_000, "MFJ", 2025) == 6_000

    def test_actc_three_child_alternative(self):
        r = ind.child_tax_credit(3, 0, 17_000, "MFJ", 0, 5_000, 2025, payroll_taxes_paid=382.50)
        assert r.refundable_actc == pytest.approx(382.50)

    def test_capital_loss_carryover_when_income_absorbs_nothing(self):
        r = prop.net_capital_gains(st_losses=2_000, lt_losses=4_000, year=2025, taxable_income=-3_000)
        assert (r.st_carryforward, r.lt_carryforward) == (2_000, 4_000)

    def test_student_loan_phaseout(self):
        from taxkit.form1040 import Return1040, compute_return
        assert compute_return(Return1040(year=2025, wages=100_000, student_loan_interest=2_500)).adjustments == 0
        assert compute_return(Return1040(year=2026, wages=92_500, student_loan_interest=2_500)).adjustments == 1_250

    def test_section_68_two_thirty_sevenths(self):
        from taxkit.form1040 import Return1040, compute_return
        r = compute_return(Return1040(year=2026, wages=800_000,
                                      itemized={"mortgage_interest": 50_000, "mortgage_avg_balance": 100_000}))
        assert r.deduction_amount == pytest.approx(47_297.30)

    def test_negative_agi_itemized(self):
        assert itm.medical_deduction(0, -10_000) == 0
        assert itm.charitable_deduction(-10_000).carryforward == 0
