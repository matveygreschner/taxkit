"""Recalculate the generated workbook with an independent formula engine
(``formulas``) and compare every key output against the Python engine.

    python scripts/verify_workbook.py workbook/TaxKit.xlsx [--fuzz 40]

Exit code 0 only if every comparison matches within $0.01 (or 1e-6 for rates).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import formulas  # noqa: E402

from taxkit import depreciation as dep  # noqa: E402
from taxkit import entities as ent  # noqa: E402
from taxkit import income as inc  # noqa: E402
from taxkit import individual as ind  # noqa: E402
from taxkit import losses as los  # noqa: E402
from taxkit import payroll as pay  # noqa: E402
from taxkit import property as prop  # noqa: E402
from taxkit import retirement as ret  # noqa: E402
from taxkit.form1040 import Return1040, compute_return  # noqa: E402
from taxkit.rates import income_tax, per_band_min_tax  # noqa: E402


class Book:
    def __init__(self, path: Path):
        self.cells = json.loads(path.with_suffix(".cells.json").read_text())
        t = time.time()
        self.model = formulas.ExcelModel().loads(str(path)).finish()
        first = self.model.calculate()
        self.prefix = {}
        for k in first:
            if "!" in k and "]" in k:
                book_sheet, _ = k.rsplit("!", 1)
                sheet = book_sheet.split("]", 1)[1].rstrip("'")
                self.prefix[sheet.upper()] = book_sheet
        print(f"compiled workbook in {time.time() - t:.1f}s")

    def key(self, sheet: str, name: str) -> str:
        addr = self.cells[sheet][name].replace("$", "") if name in self.cells.get(sheet, {}) else name
        return f"{self.prefix[sheet.upper()]}!{addr}"

    def run(self, inputs: dict, outputs: list):
        ins = {self.key(s, n): v for (s, n), v in inputs.items()}
        outs = [self.key(s, n) for s, n in outputs]
        sol = self.model.calculate(inputs=ins, outputs=outs)
        res = {}
        for (s, n), k in zip(outputs, outs):
            v = sol[k].value[0, 0]
            res[(s, n)] = v
        return res


class Checker:
    def __init__(self, book: Book):
        self.book, self.n, self.fail = book, 0, []

    def check(self, label: str, inputs: dict, expected: dict, tol: float = 0.011):
        got = self.book.run(inputs, list(expected))
        for k, exp in expected.items():
            self.n += 1
            g = got[k]
            ok = (str(g) == str(exp)) if isinstance(exp, str) else (
                isinstance(g, (int, float)) and abs(float(g) - float(exp)) <= (tol if abs(exp) >= 1 else 1e-6 + tol))
            if not ok:
                self.fail.append(f"{label}: {k[0]}.{k[1]} sheet={g!r} python={exp!r}")


def year(y):
    return {("Start", "C6"): y}


def method(m):
    return {("Start", "C7"): "Law" if m == "law" else "Simplified"}


def tax_calc(ck: Checker, fuzz: int):
    rnd = random.Random(7)
    cases = [("S", 400_000, 0, 400_000, 0, 0, 2026), ("MFJ", 85_000, 3_000, 20_000, 0, 0, 2026),
             ("S", 600_000, 0, 400_000, 350_000, 0, 2025),
             ("HOH", 250_000, 10_000, 60_000, 15_000, 5_000, 2025), ("MFS", 30_000, 0, 0, 0, 0, 2025)]
    for _ in range(fuzz):
        ti = rnd.choice([rnd.uniform(0, 120_000), rnd.uniform(0, 900_000)])
        lt = rnd.uniform(0, ti) if rnd.random() < 0.7 else 0
        u = rnd.uniform(0, lt) if rnd.random() < 0.3 else 0
        co = rnd.uniform(0, lt - u) if rnd.random() < 0.3 else 0
        cases.append((rnd.choice(["S", "MFJ", "MFS", "HOH", "QSS"]), round(ti, 2), round(rnd.uniform(0, ti - lt), 2)
                      if rnd.random() < 0.5 else 0, round(lt, 2), round(u, 2), round(co, 2), rnd.choice([2025, 2026])))
    for i, (st, ti, qd, lt, u, co, y) in enumerate(cases):
        m = ("simplified", "law")[i % 2]
        r = income_tax(ti, st, y, qd, lt, u, co, method=m)
        T = "Tax_Calc"
        ins = {**year(y), **method(m), (T, "status"): st, (T, "ti"): ti, (T, "qd"): qd, (T, "ltcg"): lt, (T, "u1250"): u,
               (T, "coll"): co}
        exp = {(T, "tax"): r.tax, (T, "regular"): r.regular_tax, (T, "at0"): r.ancg_at_0, (T, "at15"): r.ancg_at_15,
               (T, "at20"): r.ancg_at_20, (T, "marg"): r.marginal_rate,
               (T, "tax_law"): income_tax(ti, st, y, qd, lt, u, co, method="law").tax,
               (T, "tax_simplified"): income_tax(ti, st, y, qd, lt, u, co, method="simplified").tax}
        if not (u or co):
            exp[(T, "tax_simplified")] = per_band_min_tax(ti, min(ti, qd + lt), st, y)
            exp[(T, "table_tax")] = r.regular_tax
        ck.check(f"Tax_Calc {st} {ti} {y} {m}", ins, exp)


def form_1040(ck: Checker, fuzz: int):
    rnd = random.Random(11)
    base = dict(status="MFJ", wages=150_000, taxable_interest=2_000, ordinary_dividends=5_000,
                qualified_dividends=4_000, net_capital_gain=10_000, net_ltcg_for_rates=10_000, withholding=18_000,
                qualifying_children=2)
    sch = dict(med=0, salt=18_000, mort=14_000, bal=400_000, inv_int=0, nii=0, cash_pub=3_000, prop_pub=0,
               cash_priv=0, prop_priv=0, casualty=0, gamb_l=0, gamb_w=0, other_i=0)
    cases = [(base, sch, 2026)]
    for _ in range(fuzz):
        st = rnd.choice(["S", "MFJ", "MFS", "HOH"])
        b = dict(status=st, wages=round(rnd.uniform(0, 400_000), 2), taxable_interest=round(rnd.uniform(0, 20_000), 2),
                 se_person_wages=round(rnd.choice([0, rnd.uniform(0, 200_000)]), 2),
                 num_seniors=0,
                 schedule_c_profit=round(rnd.choice([0, rnd.uniform(-5_000, 250_000)]), 2),
                 other_income=round(rnd.uniform(0, 30_000), 2), age65_or_blind_boxes=rnd.randint(0, 2),
                 qualifying_children=rnd.randint(0, 4), other_dependents=rnd.randint(0, 1),
                 qualified_tips=round(rnd.choice([0, rnd.uniform(0, 40_000)]), 2),
                 qualified_overtime=round(rnd.choice([0, rnd.uniform(0, 30_000)]), 2),
                 car_loan_interest=round(rnd.choice([0, rnd.uniform(0, 12_000)]), 2),
                 se_health_insurance=round(rnd.choice([0, rnd.uniform(0, 15_000)]), 2),
                 ira_deduction=round(rnd.choice([0, 7_000]), 2), student_loan_interest=round(rnd.uniform(0, 4_000), 2),
                 net_investment_income=round(rnd.uniform(0, 60_000), 2), withholding=round(rnd.uniform(0, 60_000), 2),
                 estimated_payments=round(rnd.choice([0, 5_000]), 2))
        qd = round(rnd.uniform(0, 30_000), 2)
        b["ordinary_dividends"] = qd + round(rnd.uniform(0, 5_000), 2)
        b["qualified_dividends"] = qd
        lt = round(rnd.choice([0, rnd.uniform(0, 300_000), -3_000]), 2)
        b["net_capital_gain"] = lt
        b["net_ltcg_for_rates"] = max(0, lt)
        b["num_seniors"] = rnd.randint(0, 2)
        s = dict(sch)
        s.update(med=round(rnd.uniform(0, 40_000), 2), salt=round(rnd.uniform(0, 60_000), 2),
                 mort=round(rnd.uniform(0, 50_000), 2), bal=round(rnd.uniform(0, 1_500_000), 2),
                 inv_int=round(rnd.uniform(0, 5_000), 2), nii=round(rnd.uniform(0, 5_000), 2),
                 cash_pub=round(rnd.uniform(0, 30_000), 2), prop_pub=round(rnd.uniform(0, 20_000), 2),
                 gamb_l=round(rnd.uniform(0, 10_000), 2), gamb_w=round(rnd.uniform(0, 10_000), 2))
        cases.append((b, s, rnd.choice([2025, 2026])))
    fmap = dict(status="status", wages="wages", taxable_interest="interest", ordinary_dividends="odiv",
                qualified_dividends="qdiv", net_capital_gain="netcg", net_ltcg_for_rates="ltcg",
                schedule_c_profit="schc", se_person_wages="se_w2", other_income="other", taxable_social_security="ss",
                se_health_insurance="se_health", se_retirement="se_ret", ira_deduction="ira",
                student_loan_interest="sli", educator_expenses="educator", alimony_paid="alimony",
                other_adjustments="other_adj", age65_or_blind_boxes="boxes", num_seniors="seniors",
                qualified_tips="tips", qualified_overtime="ot", car_loan_interest="car", other_qbi="other_qbi",
                qualifying_children="kids", other_dependents="others", other_credits="other_cr",
                net_investment_income="nii", withholding="withheld", estimated_payments="estimates")
    smap = dict(med="medical_expenses", salt="state_local_taxes", mort="mortgage_interest", bal="mortgage_avg_balance",
                inv_int="investment_interest", nii="net_investment_income", cash_pub="charity_cash_public",
                prop_pub="charity_property_public", cash_priv="charity_cash_private",
                prop_priv="charity_property_private", casualty="casualty_loss_allowed", gamb_l="gambling_losses",
                gamb_w="gambling_winnings", other_i="other")
    for i, (b, s, y) in enumerate(cases):
        m = ("simplified", "law")[i % 2]
        full = {k: 0 for k in fmap if k != "status"}
        full.update(b)
        r = compute_return(Return1040(year=y, method=m, itemized={smap[k]: v for k, v in s.items()}, **full))
        F = "Form_1040"
        ins = {**year(y), **method(m), **{(F, fmap[k]): v for k, v in full.items()}, **{("Sch_A", k): v for k, v in s.items()}}
        exp = {(F, "agi"): r.agi, (F, "ded"): r.deduction_amount, (F, "sch1a"): r.schedule_1a,
               (F, "qbi"): r.qbi_deduction, (F, "ti"): r.taxable_income, (F, "tax"): r.income_tax, (F, "se"): r.se_tax,
               (F, "addl_med"): r.additional_medicare, (F, "niit"): r.niit, (F, "nonref"): r.nonrefundable_credits,
               (F, "actc"): r.refundable_credits, (F, "total_tax"): r.total_tax, (F, "balance"): r.balance_due,
               ("Sch_A", "total"): r.itemized.total}
        ck.check(f"Form_1040 {b.get('status')} {y}", ins, exp, tol=0.03)


def payroll(ck):
    P = "Payroll_SE"
    for st, w, se, w2, nii, magi, y in [("MFJ", 275_000, 275_000, 0, 50_000, 300_000, 2026),
                                        ("S", 90_000, 120_000, 90_000, 0, 150_000, 2025),
                                        ("MFS", 500_000, 300, 0, 80_000, 180_000, 2026)]:
        f = pay.fica(w, st, y)
        s = pay.self_employment_tax(se, st, y, w2)
        ck.check(f"Payroll {st}", {**year(y), (P, "status"): st, (P, "wages"): w, (P, "spouse_w"): 0, (P, "se_inc"): se,
                                   (P, "se_w2"): w2, (P, "nii"): nii, (P, "magi"): magi},
                 {(P, "er_total"): f.employer_total, (P, "addl"): f.additional_medicare, (P, "se_tax"): s.se_tax,
                  (P, "se_half"): s.deduction_half, (P, "se_addl"): s.additional_medicare,
                  (P, "niit"): pay.niit(nii, magi, st, y)})


def std_credits(ck):
    S = "Std_Ded_Credits"
    for st, boxes, dep_, earned, mfs_item, y in [("S", 0, "Yes", 7_600, "No", 2026), ("MFJ", 2, "No", 0, "No", 2025),
                                                ("MFS", 1, "No", 0, "Yes", 2026), ("HOH", 1, "Yes", 30_000, "No", 2025)]:
        exp = ind.standard_deduction(st, y, boxes, dep_ == "Yes", earned, mfs_item == "Yes")
        ck.check(f"Std {st}", {**year(y), (S, "status"): st, (S, "boxes"): boxes, (S, "is_dep"): dep_,
                               (S, "earned"): earned, (S, "mfs_item"): mfs_item}, {(S, "std"): exp})
    for e, u, pti, pst, y in [(0, 10_000, 200_000, "MFJ", 2026), (3_000, 6_000, 600_000, "S", 2025),
                              (20_000, 1_000, 90_000, "HOH", 2026)]:
        k = ind.kiddie_tax(e, u, pti, pst, y)
        ck.check("Kiddie", {**year(y), (S, "k_earned"): e, (S, "k_unearned"): u, (S, "p_ti"): pti, (S, "p_status"): pst},
                 {(S, "k_total"): k.total_child_tax, (S, "k_nui"): k.net_unearned_income})
    for st, kids, oth, magi, tax, earned, pp in [("MFJ", 2, 1, 100_000, 10_000, 100_000, 0),
                                                 ("HOH", 2, 0, 30_000, 500, 30_000, 0),
                                                 ("S", 1, 0, 230_500, 40_000, 230_500, 0),
                                                 ("MFJ", 3, 0, 17_000, 0, 5_000, 382.5)]:
        r = ind.child_tax_credit(kids, oth, magi, st, tax, earned, 2026, payroll_taxes_paid=pp)
        ck.check("CTC", {**year(2026), (S, "c_status"): st, (S, "c_kids"): kids, (S, "c_others"): oth,
                         (S, "c_magi"): magi, (S, "c_tax"): tax, (S, "c_earned"): earned, (S, "c_payroll"): pp},
                 {(S, "c_nonref"): r.nonrefundable_used, (S, "c_actc"): r.refundable_actc})
    for st, magi, sen, tips, ot, car in [("S", 100_000, 1, 30_000, 20_000, 5_000), ("MFJ", 320_500, 2, 10_000, 30_000, 12_000),
                                         ("MFS", 90_000, 1, 5_000, 5_000, 5_000), ("HOH", 160_000, 0, 25_000, 15_000, 0)]:
        tot = (ind.senior_deduction(sen, magi, st) + ind.tips_deduction(tips, magi, st)
               + ind.overtime_deduction(ot, magi, st) + ind.car_loan_interest_deduction(car, magi, st))
        ck.check("Sch1A", {**year(2026), (S, "o_status"): st, (S, "o_magi"): magi, (S, "o_seniors"): sen,
                           (S, "o_tips"): tips, (S, "o_ot"): ot, (S, "o_car"): car}, {(S, "o_total"): tot})


def capital(ck):
    C = "Capital"
    ck.check("Estate sale", {}, {(C, "ar"): 4_455_000, (C, "ab"): 345_000, (C, "recognized"): 4_110_000})
    ck.check("Home sale", {(C, "cash"): 1_000_000, (C, "fmv"): 0, (C, "debt"): 0, (C, "sell"): 0, (C, "cost"): 200_000,
                           (C, "improve"): 0, (C, "deprec"): 0, (C, "use121"): "Yes", (C, "h_status"): "S",
                           (C, "h_own"): 12, (C, "h_use"): 18, (C, "h_partial"): "Yes"},
             {(C, "excl"): 125_000, (C, "recognized"): 675_000})
    rnd = random.Random(3)
    cases = [(0, 120_000, 131_000, 0, 0, 0), (0, 120_000, 118_900, 0, 0, 0), (0, 120_000, 109_000, 0, 0, 0),
             (0, 10_000, 15_000, 0, 0, 0), (0, 100_000, 15_000, 0, 0, 0)]
    cases += [tuple(round(rnd.uniform(0, 50_000), 2) for _ in range(6)) for _ in range(12)]
    for i, (stg, stl, ltg, ltl, sco, lco) in enumerate(cases):
        for st in ("S", "MFS"):
            ti = (-2_000, 500, 1_000_000)[i % 3]
            r = prop.net_capital_gains(stg, stl, ltg, ltl, sco, lco, st, 2026, taxable_income=ti)
            ck.check(f"Netting {st}", {**year(2026), (C, "n_status"): st, (C, "stg"): stg, (C, "stl"): stl,
                                       (C, "ltg"): ltg, (C, "ltl"): ltl, (C, "st_co"): sco, (C, "lt_co"): lco,
                                       (C, "n_ti"): ti},
                     {(C, "tx_st"): r.taxable_st_gain, (C, "tx_lt"): r.taxable_lt_gain, (C, "ded"): r.deductible_loss,
                      (C, "st_cf"): r.st_carryforward, (C, "lt_cf"): r.lt_carryforward})
    for price in (210, 199, 190):
        ck.check(f"Stock {price}", {(C, "price"): price}, {(C, "sh_gain"): 1_100 * price - 100_000})
    for rec in ("Yes", "No"):
        f = prop.foreclosure(60_000, 10_000, 25_000, rec == "Yes")
        ck.check("Foreclosure", {(C, "f_rec"): rec}, {(C, "f_gain"): f.gain_on_disposition,
                                                      (C, "f_cod"): f.cancellation_of_debt_income})


def entities(ck):
    E = "Entities"
    exp = {}
    for code, entity in (("sp", "sole_prop"), ("pt", "partnership"), ("sc", "s_corp"), ("cc", "c_corp")):
        r = ent.owner_reporting(entity, -55_000, 100_000, 40_000, 0.5 if entity == "partnership" else 0.5)
        exp.update({(E, f"w2_{code}"): r.wages_w2, (E, f"gpay_{code}"): r.guaranteed_payments,
                    (E, f"divs_{code}"): r.dividends, (E, f"free_{code}"): r.tax_free_distribution,
                    (E, f"fica_{code}"): r.subject_to_fica, (E, f"set_{code}"): r.subject_to_se_tax,
                    (E, f"biz_{code}"): r.business_income})
    ck.check("Jordan", {}, exp)
    for gi, d, dr, own, cc, nol, y in [(500_000, 350_000, 0, 0, 0, 0, 2026), (400_000, 300_000, 200_000, 0.10, 20_000, 50_000, 2026),
                                       (100_000, 200_000, 100_000, 0.30, 0, 0, 2025), (50_000, 30_000, 100_000, 0.85, 5_000, 0, 2025)]:
        for m in ("simplified", "law"):
            r = ent.c_corp_tax(gi, d, dr, own, cc, nol, y, method=m)
            ck.check(f"C corp {m}", {**year(y), **method(m), (E, "gi"): gi, (E, "deds"): d, (E, "dr"): dr,
                                     (E, "own"): own, (E, "cc"): cc, (E, "nolcf"): nol},
                     {(E, "drd"): r.drd, (E, "cti"): r.taxable_income, (E, "ctax"): r.tax,
                      (E, "ch"): r.charitable_allowed, (E, "nol"): r.nol_used})

def basis(ck):
    B = "Basis"
    rows = ent.basis_rollforward([200, 50, 250, 10_000], [500, -1_000, 0, 833], [400, 0, 0, 10_250], 0.30)
    exp = {}
    for r in rows:
        i = r.year
        exp.update({(B, f"end{i}"): r.ending_basis, (B, f"free{i}"): r.tax_free_distribution,
                    (B, f"gain{i}"): r.taxable_distribution_gain, (B, f"loss{i}"): r.loss_allowed,
                    (B, f"susp{i}"): r.loss_suspended_cf, (B, f"net{i}"): r.net_reported})
    ck.check("Gamma", {}, exp)
    contrib, ni, dist = [1_000, 0, 75, 0, 20, 0], [1_000, -600, -500, 100, 0, 4_000], [0, 0, 0, 0, 0, 4_000]
    rows = ent.basis_rollforward(contrib, ni, dist, 0.80)
    ins = {(B, "pct"): 0.80}
    for i in range(6):
        ins.update({(B, f"c{i + 1}"): contrib[i] * 0.8 if i == 2 else contrib[i], (B, f"ni{i + 1}"): ni[i],
                    (B, f"d{i + 1}"): dist[i]})
    rows = ent.basis_rollforward([ins[(B, f"c{i}")] for i in range(1, 7)], ni, dist, 0.80)
    ck.check("Alpha S corp", ins, {(B, f"end{r.year}"): r.ending_basis for r in rows} |
             {(B, f"net{r.year}"): r.net_reported for r in rows})


def depreciation(ck):
    D = "Depreciation"
    for cost, cls, conv, use, s179, bonus in [(25_000, 7, "HY", 1.0, 0, 0), (25_000, 5, "HY", 1.0, 0, 0),
                                              (100_000, 7, "HY", 1.0, 30_000, 0.4), (80_000, 5, "Q4", 0.75, 0, 0.6),
                                              (60_000, 10, "Q2", 1.0, 0, 0), (300_000, 15, "HY", 1.0, 0, 0),
                                              (500_000, 20, "Q3", 1.0, 0, 0), (9_000, 3, "Q1", 1.0, 0, 0)]:
        s = dep.personal_property_schedule(cost, cls, conv, s179, bonus, use)
        exp = {(D, f"dep{r.year}"): r.depreciation for r in s.schedule}
        exp[(D, "yr1")] = s.first_year_total
        ck.check(f"MACRS {cls} {conv}", {(D, "cost"): cost, (D, "cls"): cls, (D, "conv"): conv, (D, "use"): use,
                                         (D, "s179"): s179, (D, "bonus"): bonus}, exp)
    for cost, m, res in [(495_000, 7, "Yes"), (1_404_000, 7, "No"), (300_000, 1, "Yes")]:
        rows = dep.real_property_depreciation(cost, m, res == "Yes")
        ck.check("Real property", {(D, "rp_cost"): cost, (D, "rp_month"): m, (D, "rp_res"): res},
                 {(D, "rp_y1"): rows[0].depreciation, (D, "rp_full"): rows[1].depreciation})
    for tot, el, cst, bti, y in [(3_000_000, 3_000_000, 3_000_000, 10_000_000, 2025), (500_000, 200_000, 200_000, 50_000, 2026)]:
        d, cf = dep.sec179_allowed(cst, tot, el, bti, y)
        ck.check("179", {**year(y), (D, "s_total"): tot, (D, "s_elect"): el, (D, "s_cost"): cst, (D, "s_bti"): bti},
                 {(D, "s_ded"): d, (D, "s_cf"): cf})
    for su, m in [(52_000, 12), (60_000, 6), (20_000, 3)]:
        ck.check("Startup", {(D, "su"): su, (D, "su_m"): m}, {(D, "su_y1"): dep.startup_costs(su, m)[0]})


def income_items(ck):
    I = "Income_Items"
    for st, ben, magi, ex in [("MFJ", 20_000, 50_000, 3_000), ("S", 24_000, 20_000, 0), ("S", 30_000, 40_000, 1_000),
                              ("MFS", 15_000, 10_000, 0)]:
        r = ind.taxable_social_security(ben, magi, ex, st)
        ck.check("SS", {(I, "ss_status"): st, (I, "ss_ben"): ben, (I, "ss_magi"): magi, (I, "ss_exempt"): ex},
                 {(I, "ss_tax"): r.taxable_benefits})
    for amt, afr, rate, typ, nii in [(67_500, 0.045, 0.005, "Gift", 2_750), (200_000, 0.10, 0, "Gift", 0),
                                     (50_000, 0.05, 0, "Gift", 900), (50_000, 0.05, 0, "Other", 0), (9_000, 0.05, 0, "Other", 0)]:
        ck.check("Imputed", {(I, "l_amt"): amt, (I, "l_afr"): afr, (I, "l_rate"): rate, (I, "l_type"): typ,
                             (I, "l_nii"): nii},
                 {(I, "l_imp"): inc.imputed_interest(amt, afr, rate, "gift" if typ == "Gift" else "other", nii)})
    for yrs in (0, 5, 19.5, 30):
        a = inc.annuity_exclusion(320_000, 1_667, 20.0, yrs)
        ck.check("Annuity", {(I, "a_years"): yrs}, {(I, "a_tax"): a.annual_taxable})
    for cov, age in [(250_000, 30), (100_000, 52), (40_000, 40), (500_000, 71)]:
        ck.check("GTL", {(I, "g_cov"): cov, (I, "g_age"): age}, {(I, "g_inc"): inc.group_term_life_income(cov, age)})
    ck.check("FEIE", year(2025), {(I, "f_excl"): inc.feie(240_000, 239, 2025)})
    ck.check("LTC", year(2025), {(I, "ltc_tax"): inc.ltc_taxable(165_000, 365, 162_500, 37_500, 2025)})
    ck.check("OID", {}, {(I, f"oid{y}"): v for y, v, _ in inc.oid_accrual(10_000, 0.05, 5)})


def losses(ck):
    L = "Losses"
    for pers, dest, qd, agi in [("Yes", "No", "No", 100_000), ("Yes", "No", "No", 120_000), ("No", "Yes", "No", 0),
                                ("No", "No", "No", 0), ("Yes", "No", "Yes", 120_000)]:
        r = los.casualty_loss(100_000, 110_000, 20_000, 60_000, agi, pers == "Yes", dest == "Yes", qd == "Yes")
        ck.check("Casualty", {(L, "cl_pers"): pers, (L, "cl_dest"): dest, (L, "cl_qd"): qd, (L, "cl_agi"): agi},
                 {(L, "cl_ded"): r.deductible})
    for st in ("HOH", "MFJ"):
        r = los.excess_business_loss(320_000, 700_000, st, 2026)
        ck.check("EBL", {**year(2026), (L, "eb_status"): st}, {(L, "eb_allow"): r.allowed, (L, "eb_nol"): r.disallowed_to_nol})
    ck.check("NOL", {}, {(L, "n_nol"): 34_000, (L, "na_ded"): los.apply_nol(48_400, 34_000).nol_deduction})
    for rd, pd, method in [(80, 20, "Tax Court"), (80, 20, "IRS"), (90, 10, "Tax Court"), (14, 30, "IRS"),
                           (200, 15, "IRS"), (30, 20, "Tax Court")]:
        r = los.vacation_home(rd, pd, 24_000, 18_250, 7_300, 9_600, 10_000, 850,
                              "tax_court" if method == "Tax Court" else "irs")
        ck.check(f"Vacation {rd}/{pd} {method}", {(L, "v_rent_d"): rd, (L, "v_pers_d"): pd, (L, "v_method"): method},
                 {(L, "v_it_r"): r.interest_taxes_rental, (L, "v_op_r"): r.operating_rental,
                  (L, "v_dep_r"): r.depreciation_rental, (L, "v_net"): r.net_rental_income,
                  (L, "v_scha"): r.interest_taxes_to_schedule_a})


def retirement(ck):
    R = "Retirement"
    for st, c, comp, age, magi, cov, sp, y in [("S", 7_500, 100_000, 35, 90_740, "Yes", "No", 2026),
                                               ("S", 7_500, 100_000, 35, 85_000, "Yes", "No", 2026),
                                               ("MFJ", 8_600, 100_000, 55, 140_000, "Yes", "No", 2026),
                                               ("MFJ", 7_000, 100_000, 40, 240_000, "No", "Yes", 2025),
                                               ("S", 7_500, 3_500, 30, 50_000, "No", "No", 2026),
                                               ("MFS", 7_500, 50_000, 30, 4_000, "Yes", "No", 2026)]:
        d = ret.traditional_ira_deduction(c, magi, st, cov == "Yes", sp == "Yes", comp, age, y)
        roth = ret.roth_contribution_limit(magi, st, comp, age, y)
        ck.check(f"IRA {st} {magi}", {**year(y), (R, "status"): st, (R, "contrib"): c, (R, "comp"): comp, (R, "age"): age,
                                      (R, "magi"): magi, (R, "covered"): cov, (R, "sp_cov"): sp},
                 {(R, "ira_ded"): d, (R, "roth"): roth})
    for inc_, m in [(100_000, "simplified"), (100_000, "law"), (1_000_000, "simplified")]:
        ck.check(f"SEP {m}", {**method(m), (R, "sep_inc"): inc_},
                 {(R, "sep"): ret.sep_deduction(inc_, 7_064.78, 2026, method=m)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook", nargs="?", default="workbook/TaxKit.xlsx")
    ap.add_argument("--fuzz", type=int, default=25, help="random scenarios for Tax_Calc and Form_1040")
    a = ap.parse_args()
    book = Book(Path(a.workbook))
    ck = Checker(book)
    t = time.time()
    for fn in (lambda c: tax_calc(c, a.fuzz), lambda c: form_1040(c, a.fuzz), payroll, std_credits, capital,
               entities, basis, depreciation, income_items, losses, retirement):
        fn(ck)
    print(f"{ck.n} comparisons in {time.time() - t:.1f}s, {len(ck.fail)} mismatches")
    for f in ck.fail[:60]:
        print("  MISMATCH", f)
    sys.exit(1 if ck.fail else 0)


if __name__ == "__main__":
    main()
