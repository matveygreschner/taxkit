"""Business optimizer: hand-checked entity math, Sec. 199A, and scanner behavior."""
import json
from pathlib import Path

import pytest

from taxkit.business import CompanyProfile, compare_entities, qbi_deduction_full, scan
from taxkit.business.opportunities import CHECKS

ROOT = Path(__file__).resolve().parents[1]


class TestEntityComparison:
    @pytest.fixture(scope="class")
    def res(self):
        r = compare_entities(420_000, 90_000, "MFJ", 2026, other_income=20_000, other_employee_wages=980_000,
                             ubia=600_000, state_rate=0.0575)
        return {x.entity: x for x in r}

    def test_sole_prop_se_tax(self, res):
        # 420,000 x 92.35% = 387,870; SS 12.4% x 184,500 = 22,878; Medicare 2.9% x 387,870 = 11,248.23
        assert res["sole_prop"].lines["se_tax"] == pytest.approx(34_126.23)

    def test_s_corp_k1(self, res):
        # 420,000 - 90,000 salary - 6,885 employer FICA
        assert res["s_corp"].lines["k1_income"] == pytest.approx(323_115)
        assert res["s_corp"].employer_payroll_tax == pytest.approx(6_885)

    def test_c_corp_double_tax(self, res):
        corp = res["c_corp"]
        ti = 323_115
        state = 0.0575 * ti
        assert corp.entity_income_tax == pytest.approx(0.21 * (ti - state), abs=0.01)
        assert corp.total_tax > res["s_corp"].total_tax

    def test_s_corp_beats_sole_prop_here(self, res):
        assert res["s_corp"].total_tax < res["sole_prop"].total_tax


class TestQBIFull:
    def test_below_threshold_full_20pct(self):
        d = qbi_deduction_full(100_000, 0, 0, 150_000, 0, "MFJ", year=2026)
        assert d.deduction == 20_000

    def test_income_cap(self):
        d = qbi_deduction_full(100_000, 0, 0, 60_000, 0, "S", year=2026)
        assert d.deduction == 12_000

    def test_above_range_wage_limit(self):
        # 2026 MFJ: threshold 403,500 + 150,000 range -> fully phased in at 553,500
        d = qbi_deduction_full(500_000, 80_000, 0, 700_000, 0, "MFJ", year=2026)
        assert d.deduction == 40_000          # 50% of W-2 wages < 20% of QBI (100,000)

    def test_ubia_alternative(self):
        d = qbi_deduction_full(500_000, 40_000, 2_000_000, 700_000, 0, "MFJ", year=2026)
        assert d.wage_limit == pytest.approx(max(20_000, 10_000 + 50_000))

    def test_phase_in_halfway(self):
        # 2026 single: threshold 201,750, range 75,000; halfway = 239,250
        d = qbi_deduction_full(200_000, 0, 0, 239_250, 0, "S", year=2026)
        assert d.deduction == pytest.approx(40_000 - 40_000 * 0.5)

    def test_sstb_phaseout(self):
        d = qbi_deduction_full(200_000, 0, 0, 400_000, 0, "S", sstb=True, year=2026)
        assert d.deduction == 0

    def test_2026_minimum(self):
        d = qbi_deduction_full(1_500, 0, 0, 1_000_000, 0, "S", year=2026)
        assert d.deduction == 400
        assert qbi_deduction_full(1_500, 0, 0, 1_000_000, 0, "S", year=2025).deduction == 0

    def test_2026_mfs_threshold(self):
        from taxkit.params import param
        assert param("qbi_threshold", 2026, "MFS") == 201_775


class TestScanner:
    def test_empty_profile_runs_every_check(self):
        res = scan(CompanyProfile())
        assert len(res) == len(CHECKS)

    def test_every_check_handles_zero_profile_for_each_entity(self):
        for e in ("sole_prop", "partnership", "s_corp", "c_corp"):
            for c in CHECKS:
                c(CompanyProfile(entity_type=e))

    def test_example_profile(self):
        p = CompanyProfile.from_dict(json.loads((ROOT / "examples/acme_s_corp.json").read_text()))
        res = {o.id: o for o in scan(p)}
        assert res["cost_seg"].applies and res["cost_seg"].est_savings > 0
        assert res["bonus_179"].applies                    # default 100% bonus always needs a decision
        assert "Elect out" in res["bonus_179"].summary     # this shop can't absorb it all (test-run finding)
        cap = res["deduction_capacity"]
        assert cap.applies and cap.detail["recommended_extra_deduction_this_year"] < cap.detail["total_extra_deductions"]
        assert not res["interest_163j"].applies          # small business exemption
        assert res["cash_method"].applies
        assert res["rd_credit"].detail["gross_credit"] == pytest.approx(0.14 * (140_000 - 0.5 * 320_000 / 3))
        assert res["rd_credit"].est_savings == pytest.approx(res["rd_credit"].detail["gross_credit"] * 0.79, abs=0.01)

    def test_retroactive_174a_window_not_offered_as_available(self):
        p = CompanyProfile(domestic_research_expenses=100_000, unamortized_domestic_re_2022_2024=0)
        o = next(o for o in scan(p) if o.id == "rd_174a")
        assert not o.applies                                  # 2026: expensing is the default
        assert any("closed July 6, 2026" in a for a in o.actions)

    def test_174a_two_year_catchup_second_half(self):
        p = CompanyProfile(unamortized_domestic_re_2022_2024=200_000, re_catchup_elected="two_year",
                           entity_type="c_corp", net_income_before_owner_pay=1_000_000)
        o = next(o for o in scan(p) if o.id == "rd_174a")
        assert o.applies and o.est_savings == pytest.approx(100_000 * 0.21)     # second half in 2026
        p25 = CompanyProfile(year=2025, unamortized_domestic_re_2022_2024=100_000, re_catchup_elected="two_year",
                             entity_type="c_corp", net_income_before_owner_pay=1_000_000)
        o25 = next(o for o in scan(p25) if o.id == "rd_174a")
        assert o25.est_savings == pytest.approx(50_000 * 0.21)                  # Codex case: first half only

    def test_174a_none_in_2026_not_offered(self):
        p = CompanyProfile(unamortized_domestic_re_2022_2024=200_000, re_catchup_elected="none",
                           entity_type="c_corp", net_income_before_owner_pay=1_000_000)
        o = next(o for o in scan(p) if o.id == "rd_174a")
        assert not o.applies and "2025 return" in o.summary

    def test_qsbs_tiers(self):
        base = dict(entity_type="c_corp", qsbs_eligible_stock=True, qsbs_basis=1_000_000,
                    qsbs_expected_gain=20_000_000, qsbs_gross_assets_at_issuance=30_000_000)
        pct = {}
        for yrs in (2, 3, 4, 5):
            o = next(o for o in scan(CompanyProfile(**base, qsbs_years_held_at_sale=yrs)) if o.id == "qsbs_1202")
            pct[yrs] = o.detail.get("exclusion_pct", 0)
        assert pct == {2: 0, 3: 0.5, 4: 0.75, 5: 1.0}
        o = next(o for o in scan(CompanyProfile(**base, qsbs_years_held_at_sale=5)) if o.id == "qsbs_1202")
        assert o.detail["excluded_gain"] == 15_000_000

    def test_qsbs_asset_test(self):
        o = next(o for o in scan(CompanyProfile(entity_type="c_corp", qsbs_eligible_stock=True, qsbs_expected_gain=1e6,
                                                qsbs_years_held_at_sale=5, qsbs_gross_assets_at_issuance=80e6))
                 if o.id == "qsbs_1202")
        assert not o.applies

    def test_163j_large_company(self):
        p = CompanyProfile(entity_type="c_corp", avg_gross_receipts_3yr=60e6, business_interest_expense=5e6,
                           ebitda=12e6, depreciation_amortization=4e6)
        o = next(o for o in scan(p) if o.id == "interest_163j")
        assert o.detail["limit_ebitda"] == 3.6e6 and o.detail["disallowed_now"] == pytest.approx(1.4e6)
        assert o.est_savings == pytest.approx((2.6e6 - 1.4e6) * 0.21)

    def test_childcare_small_business_2026(self):
        o = next(o for o in scan(CompanyProfile(childcare_expenses=1_000_000, avg_gross_receipts_3yr=10e6))
                 if o.id == "childcare_45f")
        assert o.est_savings == 500_000                  # 50% x $1M, cap $600K
        o = next(o for o in scan(CompanyProfile(childcare_expenses=2_000_000, avg_gross_receipts_3yr=100e6))
                 if o.id == "childcare_45f")
        assert o.est_savings == 500_000                  # 40% x $2M = $800K, capped at $500K

    def test_api_markdown(self):
        from taxkit import api
        out = api.run("business_scan", {"profile": {"entity_type": "s_corp", "net_income_before_owner_pay": 200_000,
                                                    "owner_salary": 80_000}, "format": "markdown"})
        assert "Tax opportunity scan" in out["result"]["markdown"]


class TestCodexRegressions:
    """Cases from the independent Codex review (each was a confirmed bug)."""

    def test_loss_year_wages_never_negative(self):
        for r in compare_entities(-10_000, 0, year=2025):
            assert r.owner_wages >= 0 and r.employer_payroll_tax >= 0 and r.total_tax >= 0

    def test_zero_income_c_corp_gets_no_current_depreciation_benefit(self):
        from taxkit.business import Asset
        p = CompanyProfile(entity_type="c_corp", net_income_before_owner_pay=0,
                           assets=[Asset("machine", 100_000, 5)])
        o = next(o for o in scan(p) if o.id == "bonus_179")
        assert o.detail["first_year_tax_reduction"] == 0

    def test_ptet_reflects_qbi_reduction(self):
        p = CompanyProfile(entity_type="s_corp", net_income_before_owner_pay=100_000, owner_salary=0,
                           owner_filing_status="S", state_income_tax_rate=0.05, year=2025)
        o = next(o for o in scan(p) if o.id == "ptet")
        assert o.est_savings == pytest.approx(880, abs=1)

    def test_multi_owner_qbi_allocates_wages(self):
        p = CompanyProfile(entity_type="s_corp", num_owners=2, net_income_before_owner_pay=1_000_000,
                           non_owner_wages=100_000, owner_filing_status="S", year=2025)
        o = next(o for o in scan(p) if o.id == "qbi_planning")
        assert o.detail["deduction"] == pytest.approx(25_000)

    def test_tax_shelter_not_exempt_from_163j(self):
        p = CompanyProfile(entity_type="partnership", is_tax_shelter=True, avg_gross_receipts_3yr=1e6, year=2025,
                           business_interest_expense=100_000, ebitda=100_000, net_income_before_owner_pay=100_000)
        o = next(o for o in scan(p) if o.id == "interest_163j")
        assert o.detail["limit_ebitda"] == 30_000

    def test_401k_compensation_cap(self):
        p = CompanyProfile(entity_type="s_corp", net_income_before_owner_pay=100_000, owner_salary=10_000)
        o = next(o for o in scan(p) if o.id == "retirement_plan")
        assert o.detail["max_owner_contribution"] == 10_000

    def test_childcare_five_year_test(self):
        p = CompanyProfile(childcare_expenses=100_000, avg_gross_receipts_3yr=30e6, avg_gross_receipts_5yr=38e6)
        o = next(o for o in scan(p) if o.id == "childcare_45f")
        assert o.est_savings == 40_000

    def test_oz_pre_2027_investment_has_no_deferral_value(self):
        p = CompanyProfile(capital_gain_to_reinvest=100_000, gain_realization_date="2026-03-01",
                           qof_investment_date="2026-03-15")
        o = next(o for o in scan(p) if o.id == "opportunity_zone")
        assert o.est_savings == 0

    def test_profile_validation(self):
        from taxkit import api
        bad = api.run("business_scan", {"profile": {"assets": [{"description": "x", "cost": 100, "recovery_class": 0}]}})
        assert "error" in bad
        assert "error" in api.run("business_scan", {"profile": {"capital_gain_to_reinvest": 100, "discount_rate": -1}})
        assert "error" in api.run("form_1040", {"wages": float("inf")})

    def test_extra_1040_reserved(self):
        with pytest.raises(ValueError):
            compare_entities(100_000, 40_000, extra_1040={"wages": 50_000})
