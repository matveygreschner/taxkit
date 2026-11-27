"""Estimated tax planner: safe harbors, the Form 2210 ledger, due dates and year-end remedies.

The anchor fixture is the worked example in docs/ROADMAP.md: MFJ 2025, $120K wages with $12K withheld,
$80K Schedule C, one child, four $3K estimates on time, prior year AGI $160K / tax $24K.
"""
import pytest

from taxkit import api
from taxkit.estimates import estimate_vouchers, installment_due_dates, safe_harbor, underpayment_penalty
from taxkit.estimates.projection import year_end_projection

PRIOR = {"tax": 24_000, "agi": 160_000, "status": "MFJ"}
RET = {"year": 2025, "status": "MFJ", "wages": 120_000, "schedule_c_profit": 80_000, "qualifying_children": 1,
       "withholding": 12_000}
PAYS = [{"date": d, "amount": 3_000} for d in installment_due_dates(2025)]


@pytest.fixture(scope="module")
def sh():
    return safe_harbor(31_486.92, 12_000, "MFJ", 2025, prior_year=PRIOR)


# ------------------------------------------------------------------ dates ---
class TestDueDates:
    def test_2025_june_15_is_a_sunday(self):
        assert installment_due_dates(2025) == ["2025-04-15", "2025-06-16", "2025-09-15", "2026-01-15"]

    def test_2026(self):
        assert installment_due_dates(2026) == ["2026-04-15", "2026-06-15", "2026-09-15", "2027-01-15"]

    def test_emancipation_day_pushes_april_2028(self):
        # Apr 15, 2028 is a Saturday; Emancipation Day (Sun Apr 16) is observed Mon Apr 17.
        assert installment_due_dates(2028)[0] == "2028-04-18"

    def test_mlk_day_on_jan_15(self):
        assert installment_due_dates(2028)[-1] == "2029-01-16"

    def test_farmer_single_installment(self):
        assert installment_due_dates(2025, farmer_fisherman=True) == ["2026-01-15"]


# ------------------------------------------------------------ safe harbor ---
class TestSafeHarbor:
    def test_worked_example_110pct(self, sh):
        assert sh.required_annual_payment == 26_400 and sh.ninety_pct_current == pytest.approx(28_338.23)
        assert [i["required"] for i in sh.installments] == [6_600] * 4

    @pytest.mark.parametrize("agi, pct", [(150_000.00, 1.00), (150_000.01, 1.10)])
    def test_150k_boundary(self, agi, pct):
        r = safe_harbor(100_000, 0, "MFJ", 2025, prior_year={"tax": 50_000, "agi": agi, "status": "MFJ"})
        assert r.prior_year_pct == pct

    def test_mfs_75k_threshold(self):
        r = safe_harbor(100_000, 0, "MFS", 2025, prior_year={"tax": 50_000, "agi": 80_000, "status": "MFS"})
        assert r.prior_year_pct == 1.10

    @pytest.mark.parametrize("wh, exempt", [(11_000.01, True), (11_000.00, False)])
    def test_1000_exception(self, wh, exempt):
        assert safe_harbor(12_000, wh, "S", 2025).exempt is exempt

    def test_zero_prior_tax_exception(self):
        ok = safe_harbor(50_000, 0, "S", 2025, prior_year={"tax": 0, "agi": 0, "status": "S"})
        assert ok.exempt and "6654(e)(2)" in ok.exemption
        nra = safe_harbor(50_000, 0, "S", 2025, prior_year={"tax": 0, "agi": 0}, citizen_or_resident=False)
        assert not nra.exempt
        short = safe_harbor(50_000, 0, "S", 2025, prior_year={"tax": 0, "agi": 0, "full_12_months": False})
        assert not short.exempt and short.method.startswith("90%")

    def test_no_prior_year(self):
        r = safe_harbor(40_000, 0, "S", 2025)
        assert r.required_annual_payment == 36_000 and any("No prior-year" in n for n in r.notes)

    def test_mfj_after_separate_returns(self):
        r = safe_harbor(80_000, 0, "MFJ", 2025,
                        prior_year={"tax": 20_000, "agi": 100_000, "status": "MFS", "spouse_separate_tax": 10_000})
        assert r.prior_year_amount == 30_000
        with pytest.raises(ValueError):
            safe_harbor(80_000, 0, "MFJ", 2025, prior_year={"tax": 20_000, "agi": 100_000, "status": "MFS"})

    def test_mfs_after_joint_return_allocates(self):
        r = safe_harbor(40_000, 0, "MFS", 2025, prior_year={"tax": 30_000, "agi": 60_000, "status": "MFJ",
                                                            "own_separate_tax": 12_000, "spouse_separate_tax": 24_000})
        assert r.prior_year_amount == pytest.approx(10_000)

    def test_farmer(self):
        r = safe_harbor(30_000, 0, "S", 2025, farmer_fisherman=True)
        assert r.required_annual_payment == pytest.approx(20_000) and len(r.installments) == 1

    def test_jan31_excuses_q4(self):
        r = safe_harbor(31_486.92, 12_000, "MFJ", 2025, prior_year=PRIOR, filed_and_paid_by_jan31=True)
        pen = underpayment_penalty(r.installments, PAYS, 12_000, 2025)
        assert pen.rows[3].penalty == 0 and pen.total_penalty == pytest.approx(110.63 - 40.44)


# ---------------------------------------------------------------- penalty ---
class TestPenaltyLedger:
    def test_worked_example(self, sh):
        r = underpayment_penalty(sh.installments, PAYS, 12_000, 2025)
        assert [row.penalty for row in r.rows] == [7.13, 20.94, 42.12, 40.44]
        assert r.total_penalty == pytest.approx(110.63)

    def test_rate_change_inside_a_shortfall(self, sh):
        last = underpayment_penalty(sh.installments, PAYS, 12_000, 2025).rows[3]
        assert [(s.days, s.rate) for s in last.segments] == [(75, 0.07), (15, 0.06)]

    def test_december_withholding_cures_everything(self, sh):
        assert underpayment_penalty(sh.installments, PAYS, 14_400, 2025).total_penalty == 0

    def test_jan15_payment_only_fixes_q4(self, sh):
        extra = PAYS + [{"date": "2026-01-15", "amount": 2_400}]
        assert underpayment_penalty(sh.installments, extra, 12_000, 2025).total_penalty == pytest.approx(70.19)

    def test_day_count_convention(self):
        inst = [{"due": "2025-04-15", "required": 10_000}]
        on_time = underpayment_penalty(inst, [{"date": "2025-04-15", "amount": 10_000}], year=2025)
        one_late = underpayment_penalty(inst, [{"date": "2025-04-16", "amount": 10_000}], year=2025)
        assert on_time.total_penalty == 0
        assert one_late.rows[0].segments[0].days == 1
        assert one_late.total_penalty == pytest.approx(round(10_000 * 0.07 / 365, 2))

    def test_accrual_stops_april_15(self):
        inst = [{"due": "2025-04-15", "required": 10_000}]
        late = underpayment_penalty(inst, [{"date": "2026-06-30", "amount": 10_000}], year=2025)
        assert late.rows[0].segments[-1].end == "2026-04-15"
        assert sum(s.days for s in late.rows[0].segments) == 365

    def test_earliest_first_application(self):
        inst = [{"due": "2025-04-15", "required": 1_000}, {"due": "2025-06-16", "required": 1_000}]
        r = underpayment_penalty(inst, [{"date": "2025-06-16", "amount": 2_000}], year=2025)
        assert r.rows[0].applied[0]["amount"] == 1_000      # Q2 payment first cures Q1
        assert r.rows[1].penalty == 0 and r.rows[0].penalty > 0

    def test_postponement_window(self):
        inst = [{"due": "2025-04-15", "required": 1_000}]
        r = underpayment_penalty(inst, [{"date": "2025-10-15", "amount": 1_000}], year=2025,
                                 postponements=[{"start": "2025-01-07", "end": "2025-10-15"}])
        assert r.total_penalty == 0 and any("7508A" in n for n in r.notes)

    def test_refuses_unknown_rate(self):
        inst = [{"due": "2027-01-15", "required": 1_000}]
        with pytest.raises(ValueError, match="2027Q1"):
            underpayment_penalty(inst, [], year=2026)

    def test_override_and_projection_are_labeled(self):
        inst = [{"due": "2027-01-15", "required": 1_000}]
        o = underpayment_penalty(inst, [], year=2026, rate_overrides={"2027Q1": 0.07, "2027Q2": 0.07})
        assert not o.projected and o.rate_sources["2027Q1"].startswith("caller-supplied")
        p = underpayment_penalty(inst, [], year=2026, rate_assumption="hold_last")
        assert p.projected and p.rate_sources["2027Q1"].startswith("PROJECTED")

    @pytest.mark.parametrize("extra", [0, 100, 1_000, 5_000])
    def test_extra_payment_never_raises_penalty(self, sh, extra):
        base = underpayment_penalty(sh.installments, PAYS, 12_000, 2025).total_penalty
        more = underpayment_penalty(sh.installments, PAYS + [{"date": "2025-09-15", "amount": extra}], 12_000, 2025)
        assert more.total_penalty <= base

    def test_paying_earlier_never_raises_penalty(self, sh):
        late = underpayment_penalty(sh.installments, PAYS + [{"date": "2025-12-01", "amount": 1_000}], 12_000, 2025)
        early = underpayment_penalty(sh.installments, PAYS + [{"date": "2025-07-01", "amount": 1_000}], 12_000, 2025)
        assert early.total_penalty <= late.total_penalty

    def test_linear_within_one_rate_period(self):
        inst = [{"due": "2025-04-15", "required": 10_000}]
        a = underpayment_penalty(inst, [{"date": "2025-06-15", "amount": 10_000}], year=2025).total_penalty
        inst2 = [{"due": "2025-04-15", "required": 20_000}]
        b = underpayment_penalty(inst2, [{"date": "2025-06-15", "amount": 20_000}], year=2025).total_penalty
        assert b == pytest.approx(2 * a, abs=0.01)


# --------------------------------------------------------------- vouchers ---
def test_vouchers():
    v = estimate_vouchers(26_400, 12_000, 2025)
    assert v["total_estimates"] == 14_400 and [x["amount"] for x in v["vouchers"]] == [3_600] * 4


# ------------------------------------------------------------- projection ---
class TestYearEndProjection:
    @pytest.fixture(scope="class")
    def proj(self):
        return year_end_projection(RET, PAYS, as_of="2025-11-26", prior_year=PRIOR, taxpayer_age=40,
                                   ira={"balance": 500_000, "rollover_dates_last_12_months": [],
                                        "cash_available_for_60_days": 5_000})

    def test_uses_full_1040(self, proj):
        assert proj.projected_total_tax == pytest.approx(31_486.92)
        assert proj.balance_due_at_filing == pytest.approx(7_486.92)
        assert proj.penalty_if_nothing_changes == pytest.approx(110.63)

    def test_ranking(self, proj):
        names = [m.name for m in proj.remedies]
        assert names[0].startswith("Extra federal withholding") and proj.remedies[0].amount == 2_400
        kept = next(m for m in proj.remedies if "kept" in m.name)
        assert not kept.recommended and names[-1] == kept.name
        assert kept.cost == pytest.approx(7_680, abs=1)           # 22% + 10% on $24,000
        jan = next(m for m in proj.remedies if m.name.startswith("Estimated payment"))
        assert jan.penalty_after == pytest.approx(70.19)

    def test_ira_default_10pct_sizing(self, proj):
        roll = next(m for m in proj.remedies if "10% default" in m.name)
        assert roll.amount == 24_000 and roll.recommended
        hundred = next(m for m in proj.remedies if "100% withholding" in m.name)
        assert hundred.amount == 2_400                     # W-4R election shown as its own option

    def test_w4_ranks_above_equal_ira_rollover(self, proj):
        assert proj.remedies[0].name.startswith("Extra federal withholding")
        assert proj.remedies[1].name.startswith("IRA distribution with 100%")

    def test_ira_100pct_election(self):
        p = year_end_projection(RET, PAYS, as_of="2025-11-26", prior_year=PRIOR, taxpayer_age=40,
                                ira={"balance": 500_000, "cash_available_for_60_days": 5_000, "withholding_rate": 1.0})
        rolls = [m for m in p.remedies if "rolled back" in m.name]
        assert len(rolls) == 1 and rolls[0].amount == 2_400

    def test_rollover_rejected_for_cash_and_12_months(self):
        cash = year_end_projection(RET, PAYS, as_of="2025-11-26", prior_year=PRIOR,
                                   ira={"balance": 500_000, "cash_available_for_60_days": 2_399})
        assert not next(m for m in cash.remedies if "10% default" in m.name).recommended
        recent = year_end_projection(RET, PAYS, as_of="2025-11-26", prior_year=PRIOR,
                                     ira={"balance": 500_000, "cash_available_for_60_days": 10_000,
                                          "rollover_dates_last_12_months": ["2025-03-01"]})
        for roll in (m for m in recent.remedies if "rolled back" in m.name):
            assert not roll.recommended and any("408(d)(3)(B)" in c for c in roll.caveats)

    def test_no_ira_input(self):
        p = year_end_projection(RET, PAYS, as_of="2025-11-26", prior_year=PRIOR)
        assert any("not evaluated" in n for n in p.notes) and not any("IRA" in m.name for m in p.remedies)

    def test_exempt_case(self):
        p = year_end_projection({"year": 2025, "status": "S", "wages": 60_000, "withholding": 9_000}, [],
                                as_of="2025-11-26")
        assert p.safe_harbor["exempt"] and p.remedies == []

    def test_2026_needs_2027_rates(self):
        r = {"year": 2026, "status": "S", "wages": 100_000, "withholding": 5_000}
        with pytest.raises(ValueError, match="2027Q1"):
            year_end_projection(r, [], as_of="2026-11-26")
        p = year_end_projection(r, [], as_of="2026-11-26", rate_assumption="hold_last")
        assert p.projected_rates and p.penalty_if_nothing_changes > 0

    def test_api(self):
        out = api.run("year_end_projection", {"return_inputs": RET, "estimated_payments": PAYS,
                                              "as_of": "2025-11-26", "prior_year": PRIOR})
        assert out["result"]["penalty_if_nothing_changes"] == pytest.approx(110.63)
        assert "error" in api.run("underpayment_penalty", {"required_installments": [{"due": "2027-01-15",
                                                                                      "required": 1}], "year": 2026})
